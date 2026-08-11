"""Pure parsers for operation-registry source facts.

This module accepts source bytes and returns data.  It never imports or executes
code from the router checkout, and it performs no filesystem I/O.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping


class OperationSourceParseError(ValueError):
    """A required static source fact is missing, ambiguous, or malformed."""


class PatchFamilyDispatchMismatch(OperationSourceParseError):
    """A patch family advertises native operations it does not actually route."""


class NativeAdmissionContractMismatch(OperationSourceParseError):
    """Native entrypoint admission semantics differ from the security contract."""


@dataclass(frozen=True)
class NativeFamilyFacts:
    key: str
    file_name: str
    hasop_fn: str
    label: str
    operations: frozenset[str]
    dispatch_fn: str
    dispatch_operations: frozenset[str]
    unresolved: tuple[str, ...]


@dataclass(frozen=True)
class NativeSourceFacts:
    families: Mapping[str, NativeFamilyFacts]
    runtime_family_gates: tuple[str, ...]
    runtime_family_dispatchers: tuple[str, ...]
    legacy_dispatch_operations: frozenset[str]
    native_table_operation_families: Mapping[str, str]
    internal_table_operation_families: Mapping[str, str]
    duplicate_native_table_operations: tuple[str, ...]
    duplicate_internal_table_operations: tuple[str, ...]

    @property
    def native_table_operations(self) -> frozenset[str]:
        return frozenset(self.native_table_operation_families)

    @property
    def internal_table_operations(self) -> frozenset[str]:
        return frozenset(self.internal_table_operation_families)

    @property
    def discovered_family_gates(self) -> frozenset[str]:
        return frozenset(family.hasop_fn for family in self.families.values())

    @property
    def coded_operations(self) -> frozenset[str]:
        operations = set(self.native_table_operations)
        for family in self.families.values():
            operations.update(family.operations)
        return frozenset(operations)


_OPERATION_TABLE_ROW_RE = re.compile(
    r'\{\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\}'
)
_CPP_STRING_CONSTANT_RE = re.compile(
    r'^[ \t]*(?:static[ \t]+)?const[ \t]+char[ \t]*\*[ \t]*const[ \t]+'
    r'([A-Za-z_]\w*)[ \t]*=[ \t]*"([A-Za-z0-9_.-]+)"[ \t]*;[ \t]*\r?$',
    re.MULTILINE,
)
M08_FAMILY_TOKENS = ("c", "d", "e", "f", "g", "h", "k", "kc", "l", "m", "n")
NON_M08_FAMILY_SPECS = (
    ("w6_layerstate", "w6_layerstate_handlers.inc", "w6LayerStateHasOp", "w6-layerstate"),
    ("w6_dynblk", "w6_dynblk_handlers.inc", "w6dynblkHasOp", "w6-dynblk"),
    ("w6_section", "w6_section_handlers.inc", "w6sectionHasOp", "w6-section"),
    ("w7_materials", "materials_read.inc", "materialsReadHasOp", "w7-materials"),
    ("w7_annoscale", "annoscale_read.inc", "annoscaleReadHasOp", "w7-annoscale"),
)
_NON_M08_FAMILIES = {
    file_name: (key, hasop_fn, label)
    for key, file_name, hasop_fn, label in NON_M08_FAMILY_SPECS
}
_SUPPORTED_FAMILIES = {
    **{
        f"m08{token}_handlers.inc": (
            token,
            f"m08{token}HasOp",
            f"m08{token}",
        )
        for token in M08_FAMILY_TOKENS
    },
    **_NON_M08_FAMILIES,
}
_SUPPORTED_AUXILIARY_FAMILY_INCLUDES = frozenset({"e2_display_oracle.inc"})


def _decode_utf8(source: bytes, label: str) -> str:
    try:
        return source.decode("utf-8-sig", errors="strict")
    except UnicodeError as exc:
        raise OperationSourceParseError(f"{label} is not strict UTF-8: {exc}") from exc


def _strip_cpp_comments(source: str) -> str:
    """Remove C/C++ comments while preserving strings, escapes, and newlines."""

    output: list[str] = []
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        character = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if character in {'"', "'"}:
                quote = character
                state = "string"
                output.append(character)
            elif character == "/" and following == "/":
                state = "line_comment"
                output.extend((" ", " "))
                index += 1
            elif character == "/" and following == "*":
                state = "block_comment"
                output.extend((" ", " "))
                index += 1
            else:
                output.append(character)
        elif state == "string":
            output.append(character)
            if character == "\\" and following:
                output.append(following)
                index += 1
            elif character == quote:
                state = "code"
        elif state == "line_comment":
            if character in "\r\n":
                output.append(character)
                state = "code"
            else:
                output.append(" ")
        else:  # block_comment
            if character == "*" and following == "/":
                output.extend((" ", " "))
                index += 1
                state = "code"
            elif character in "\r\n":
                output.append(character)
            else:
                output.append(" ")
        index += 1
    if state == "block_comment":
        raise OperationSourceParseError("C++ source contains an unterminated block comment")
    return "".join(output)


def _matching_delimiter(
    text: str,
    start: int,
    opening: str,
    closing: str,
    label: str,
) -> int:
    if start >= len(text) or text[start] != opening:
        raise OperationSourceParseError(f"{label} has no opening {opening!r}")
    depth = 0
    state = "code"
    quote = ""
    index = start
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if character in {'"', "'"}:
                state = "string"
                quote = character
            elif character == opening:
                depth += 1
            elif character == closing:
                depth -= 1
                if depth == 0:
                    return index
        else:
            if character == "\\" and following:
                index += 1
            elif character == quote:
                state = "code"
        index += 1
    raise OperationSourceParseError(f"{label} has an unbalanced {opening!r}")


def _function_body(
    text: str,
    function_name: str,
    label: str,
    *,
    return_type: str = r"bool",
) -> str:
    definitions = list(re.finditer(
        r"\b(?:static\s+)?" + return_type + r"\s+"
        + re.escape(function_name) + r"\s*\([^()]*\)\s*\{",
        text,
    ))
    if len(definitions) != 1:
        raise OperationSourceParseError(
            f"{label} must have exactly one parseable {function_name}() definition"
        )
    start = definitions[0].end() - 1
    end = _matching_delimiter(
        text, start, "{", "}", f"{label} {function_name}() body"
    )
    return text[start + 1 : end]


def _curly_depths_at(text: str, positions: tuple[int, ...]) -> dict[int, int]:
    wanted = set(positions)
    depths: dict[int, int] = {}
    depth = 0
    state = "code"
    quote = ""
    index = 0
    while index < len(text):
        if index in wanted:
            depths[index] = depth
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if character in {'"', "'"}:
                state = "string"
                quote = character
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth < 0:
                    raise OperationSourceParseError("C++ source has an unmatched '}'")
        else:
            if character == "\\" and following:
                index += 1
            elif character == quote:
                state = "code"
        index += 1
    if depth != 0:
        raise OperationSourceParseError("C++ source has unbalanced braces")
    return depths


def _translation_unit_string_constants(text: str, label: str) -> dict[str, str]:
    declarations = list(_CPP_STRING_CONSTANT_RE.finditer(text))
    depths = _curly_depths_at(text, tuple(match.start() for match in declarations))
    by_name: dict[str, list[tuple[int, str]]] = {}
    for declaration in declarations:
        by_name.setdefault(declaration.group(1), []).append(
            (depths[declaration.start()], declaration.group(2))
        )
    duplicate_names = sorted(
        name for name, values in by_name.items() if len(values) != 1
    )
    if duplicate_names:
        raise OperationSourceParseError(
            f"{label} has duplicate C++ string constant declarations: "
            f"{duplicate_names!r}"
        )
    return {
        name: declarations_for_name[0][1]
        for name, declarations_for_name in by_name.items()
        if declarations_for_name[0][0] == 0
    }


def _remove_supported_preprocessor_lines(
    body: str,
    label: str,
) -> str:
    allowed_macros: set[str] = set()
    if label.endswith("m08d_handlers.inc"):
        allowed_macros.add("ARIADNE_M08D_BREP")
    if label.endswith("m08n_handlers.inc"):
        allowed_macros.add("AcEdAds_Deprecated_ACHAR_Funcs")

    stack: list[str] = []
    output: list[str] = []
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped.startswith("#"):
            output.append(line)
            continue
        opening = re.fullmatch(r"#ifdef\s+([A-Za-z_]\w*)", stripped)
        if opening is not None and opening.group(1) in allowed_macros:
            stack.append(opening.group(1))
            output.append("\n" if line.endswith("\n") else "")
            continue
        if stripped == "#else" and stack:
            output.append("\n" if line.endswith("\n") else "")
            continue
        if re.fullmatch(r"#endif(?:\s*//.*)?", stripped) and stack:
            stack.pop()
            output.append("\n" if line.endswith("\n") else "")
            continue
        raise OperationSourceParseError(
            f"{label} has an unsupported preprocessor directive in an "
            f"operation-authority body: {stripped!r}"
        )
    if stack:
        raise OperationSourceParseError(
            f"{label} has unbalanced supported preprocessor directives"
        )
    return "".join(output)


def _family_spec(file_name: str) -> tuple[str, str, str] | None:
    return _SUPPORTED_FAMILIES.get(file_name)


def _validate_family_preprocessor(text: str, label: str) -> None:
    if not label.endswith("m08d_handlers.inc"):
        return
    macro = "ARIADNE_M08D_BREP"
    directives = [
        (line_number, line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.lstrip().startswith("#")
    ]
    definitions = [
        line_number for line_number, directive in directives
        if directive == f"#define {macro} 1"
    ]
    conflicting = [
        (line_number, directive)
        for line_number, directive in directives
        if re.match(rf"#(?:define|undef)\s+{re.escape(macro)}\b", directive)
        and directive != f"#define {macro} 1"
    ]
    if len(definitions) != 1 or conflicting:
        raise OperationSourceParseError(
            f"{label} must define {macro} exactly once and unconditionally as 1; "
            f"definitions={definitions!r}; conflicting={conflicting!r}"
        )
    stack: list[tuple[str, int]] = []
    first_guard_line: int | None = None
    for line_number, directive in directives:
        conditional = re.match(r"#(if|ifdef|ifndef|elif|else|endif)\b(.*)", directive)
        if conditional is None:
            continue
        kind, remainder = conditional.groups()
        if kind == "ifdef" and remainder.strip() == macro:
            if first_guard_line is None:
                first_guard_line = line_number
            stack.append((macro, line_number))
            continue
        if kind == "endif" and stack:
            stack.pop()
            continue
        raise OperationSourceParseError(
            f"{label} has unsupported conditional preprocessor state for {macro}: "
            f"line {line_number}: {directive!r}"
        )
    if stack or first_guard_line is None or definitions[0] >= first_guard_line:
        raise OperationSourceParseError(
            f"{label} has ambiguous or unbalanced {macro} guard state"
        )


def _native_operation_authority_includes(native_job: str) -> tuple[str, ...]:
    start_marker = "struct AriadneOperationSpec"
    end_marker = "static void ariadneNativeJobWithScope"
    if native_job.count(start_marker) != 1 or native_job.count(end_marker) != 1:
        raise OperationSourceParseError(
            "AriadneNativeJob.cpp has ambiguous native operation authority boundaries"
        )
    start = native_job.index(start_marker)
    end = native_job.index(end_marker, start)
    authority = native_job[start:end]
    includes: list[str] = []
    for line in authority.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        include = re.fullmatch(
            r'#include\s+"(families/([A-Za-z0-9_.-]+\.inc))"',
            stripped,
        )
        if include is None:
            raise OperationSourceParseError(
                "AriadneNativeJob.cpp operation authority has an unsupported "
                f"preprocessor directive: {stripped!r}"
            )
        relative_path, file_name = include.groups()
        if (
            _family_spec(file_name) is None
            and file_name not in _SUPPORTED_AUXILIARY_FAMILY_INCLUDES
        ):
            raise OperationSourceParseError(
                "AriadneNativeJob.cpp operation authority includes unsupported "
                f"family source {relative_path!r}"
            )
        includes.append(relative_path)
    if not includes or len(includes) != len(set(includes)):
        raise OperationSourceParseError(
            "AriadneNativeJob.cpp operation authority family includes are empty "
            "or duplicated"
        )
    return tuple(includes)


def _mask_cpp_string_literals(source: str) -> str:
    """Mask string/character contents while preserving source offsets."""

    output = list(source)
    state = "code"
    quote = ""
    index = 0
    while index < len(source):
        character = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if character in {'"', "'"}:
                state = "string"
                quote = character
                output[index] = " "
        else:
            output[index] = " "
            if character == "\\" and following:
                output[index + 1] = " "
                index += 1
            elif character == quote:
                state = "code"
        index += 1
    if state != "code":
        raise OperationSourceParseError("C++ source contains an unterminated literal")
    return "".join(output)


def _split_cpp_call_arguments(arguments: str, label: str) -> tuple[str, ...]:
    if not arguments.strip():
        return ()
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    state = "code"
    quote = ""
    index = 0
    while index < len(arguments):
        character = arguments[index]
        following = arguments[index + 1] if index + 1 < len(arguments) else ""
        if state == "code":
            if character in {'"', "'"}:
                state = "string"
                quote = character
            elif character in "([{":
                stack.append(character)
            elif character in ")]}":
                if not stack or stack[-1] != pairs[character]:
                    raise OperationSourceParseError(
                        f"{label} has unbalanced call arguments"
                    )
                stack.pop()
            elif character == "," and not stack:
                parts.append(arguments[start:index].strip())
                start = index + 1
        else:
            if character == "\\" and following:
                index += 1
            elif character == quote:
                state = "code"
        index += 1
    if state != "code" or stack:
        raise OperationSourceParseError(f"{label} has unbalanced call arguments")
    parts.append(arguments[start:].strip())
    if any(not part for part in parts):
        raise OperationSourceParseError(f"{label} has an empty call argument")
    return tuple(parts)


def _entrypoint_admission_calls(
    body: str,
    function_name: str,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return calls whose direct arguments contain an admission-scope member."""

    source = _strip_cpp_comments(body)
    masked = _mask_cpp_string_literals(source)
    calls: list[tuple[str, tuple[str, ...]]] = []
    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", masked):
        target = match.group(1)
        opening = masked.find("(", match.start(), match.end())
        closing = _matching_delimiter(
            source,
            opening,
            "(",
            ")",
            f"AriadneNativeJob.cpp {function_name}() {target}() call",
        )
        arguments = _split_cpp_call_arguments(
            source[opening + 1 : closing],
            f"AriadneNativeJob.cpp {function_name}() {target}() call",
        )
        compact_arguments = tuple(re.sub(r"\s+", "", item) for item in arguments)
        if any(
            re.fullmatch(
                r"AriadneOperationAdmissionScope::[A-Za-z_]\w*",
                item,
            )
            for item in compact_arguments
        ):
            calls.append((target, compact_arguments))
    return tuple(calls)


def _validate_native_admission_contract(native_job: str) -> None:
    try:
        admission_body = _function_body(
            native_job,
            "isAriadneNativeOperationAdmitted",
            "AriadneNativeJob.cpp",
        )
        normalized = " ".join(admission_body.split())
        expected = " ".join("""
            const bool publicOperation = findAriadneNativeOp(op) != nullptr
                || familyHasOp(op);
            const bool internalOperation = findAriadneInternalOp(op) != nullptr;
            switch (scope) {
            case AriadneOperationAdmissionScope::PublicOnly:
                return publicOperation;
            case AriadneOperationAdmissionScope::PublicOrDiagnosticInternal:
                return publicOperation
                    || (internalOperation && op != "e2.inspect.xclip_membership");
            case AriadneOperationAdmissionScope::E2ReadOnlyOnly:
                return internalOperation && op == "e2.inspect.xclip_membership";
            }
            return false;
        """.split())
        if normalized != expected:
            raise NativeAdmissionContractMismatch(
                "isAriadneNativeOperationAdmitted must preserve exact PublicOnly, "
                "PublicOrDiagnosticInternal, and E2ReadOnlyOnly semantics"
            )

        public = "AriadneOperationAdmissionScope::PublicOnly"
        diagnostic = (
            "AriadneOperationAdmissionScope::PublicOrDiagnosticInternal"
        )
        read_only = "AriadneOperationAdmissionScope::E2ReadOnlyOnly"
        entrypoint_calls = {
            "ariadneNativeJob": (
                ("ariadneNativeJobWithScope", (public,)),
            ),
            "ariadneNativeJobArgs": (
                ("ariadneNativeJobWithScope", (diagnostic,)),
                ("ariadneNativeJobWithScope", (diagnostic,)),
            ),
            "ariadneNativeJobArgsReadOnly": (
                (
                    "isAriadneNativeOperationAdmitted",
                    ("operation", read_only),
                ),
                (
                    "ariadneNativeJobResult",
                    ("immutableJob", "host", "nullptr", read_only),
                ),
                (
                    "ariadneNativeJobResult",
                    (
                        "immutableJob",
                        "host",
                        "openedDocument->database()",
                        read_only,
                    ),
                ),
            ),
            "ariadneNativeJobMailbox": (
                ("ariadneNativeJobWithScope", (diagnostic,)),
            ),
        }
        for function_name, expected_calls in entrypoint_calls.items():
            body = _function_body(
                native_job,
                function_name,
                "AriadneNativeJob.cpp",
                return_type=r"void",
            )
            observed_calls = _entrypoint_admission_calls(body, function_name)
            if observed_calls != expected_calls:
                raise NativeAdmissionContractMismatch(
                    f"{function_name} admission calls mismatch: "
                    f"expected={expected_calls!r}; observed={observed_calls!r}"
                )
    except NativeAdmissionContractMismatch:
        raise
    except OperationSourceParseError as exc:
        raise NativeAdmissionContractMismatch(str(exc)) from exc


def _parse_operation_table(
    source: str,
    table_name: str,
) -> tuple[dict[str, str], tuple[str, ...]]:
    table_matches = list(re.finditer(
        re.escape(table_name) + r"\[\]\s*=\s*\{(.*?)\};",
        source,
        re.S,
    ))
    if len(table_matches) != 1:
        raise OperationSourceParseError(
            f"AriadneNativeJob.cpp must define {table_name} exactly once; "
            f"observed={len(table_matches)}"
        )
    table_body = table_matches[0].group(1)
    rows = _OPERATION_TABLE_ROW_RE.findall(table_body)
    if not rows:
        raise OperationSourceParseError(f"{table_name} is empty")
    unparsed = _OPERATION_TABLE_ROW_RE.sub("", table_body)
    unparsed = re.sub(r"//[^\r\n]*", "", unparsed)
    if unparsed.strip(" \t\r\n,"):
        raise OperationSourceParseError(
            f"{table_name} contains an unparseable row"
        )
    families: dict[str, str] = {}
    duplicates: set[str] = set()
    for operation_id, family in rows:
        if operation_id in families:
            duplicates.add(operation_id)
        families[operation_id] = family
    return families, tuple(sorted(duplicates))


def _validate_native_table_lookup_contract(native_job: str) -> None:
    """Bind operation tables to the only supported count/lookup grammar."""

    lookup_specs = (
        (
            "kAriadneNativeOperationTable",
            "kAriadneNativeOperationCount",
            "findAriadneNativeOp",
        ),
        (
            "kAriadneInternalOperationTable",
            "kAriadneInternalOperationCount",
            "findAriadneInternalOp",
        ),
    )
    for table_name, count_name, function_name in lookup_specs:
        count_pattern = re.compile(
            r"\bstatic\s+const\s+size_t\s+"
            + re.escape(count_name)
            + r"\s*=\s*sizeof\s*\(\s*"
            + re.escape(table_name)
            + r"\s*\)\s*/\s*sizeof\s*\(\s*"
            + re.escape(table_name)
            + r"\s*\[\s*0\s*\]\s*\)\s*;"
        )
        if len(count_pattern.findall(native_job)) != 1:
            raise OperationSourceParseError(
                f"AriadneNativeJob.cpp {count_name} must use the canonical "
                f"sizeof({table_name}) table count"
            )

        body = _function_body(
            native_job,
            function_name,
            "AriadneNativeJob.cpp",
            return_type=r"const\s+AriadneOperationSpec\s*\*",
        )
        normalized = " ".join(body.split())
        expected = " ".join(f"""
            for (size_t i = 0; i < {count_name}; ++i) {{
                if (op == {table_name}[i].op_id)
                    return &{table_name}[i];
            }}
            return nullptr;
        """.split())
        if normalized != expected:
            raise OperationSourceParseError(
                f"AriadneNativeJob.cpp {function_name} must preserve the "
                f"canonical table lookup for {table_name}"
            )

    known_body = _function_body(
        native_job,
        "isAriadneNativeOperationKnown",
        "AriadneNativeJob.cpp",
    )
    normalized_known = " ".join(known_body.split())
    expected_known = " ".join("""
        return findAriadneNativeOp(op) != nullptr
            || findAriadneInternalOp(op) != nullptr
            || familyHasOp(op);
    """.split())
    if normalized_known != expected_known:
        raise OperationSourceParseError(
            "AriadneNativeJob.cpp isAriadneNativeOperationKnown must bind the "
            "public table, internal table, and family gate exactly once"
        )


def parse_hasop_operations(
    source: bytes,
    hasop_fn: str,
    label: str,
) -> tuple[frozenset[str], tuple[str, ...]]:
    """Parse one C++ HasOp function without executing or compiling source."""

    text = _strip_cpp_comments(_decode_utf8(source, label))
    _validate_family_preprocessor(text, label)
    body = _function_body(text, hasop_fn, label)
    body = _remove_supported_preprocessor_lines(body, label)
    constants = _translation_unit_string_constants(text, label)
    match = re.fullmatch(
        r"\s*(?:\(void\)\s*op\s*;\s*)?return\s+(.+?)\s*;\s*",
        body,
        flags=re.S,
    )
    if match is None:
        raise OperationSourceParseError(
            f"{label} {hasop_fn}() is not one direct return expression"
        )
    expression = match.group(1).strip()
    operations: set[str] = set()
    unresolved: list[str] = []
    for term in expression.split("||"):
        term = term.strip()
        if term == "false":
            continue
        term_match = re.fullmatch(
            r'op\s*==\s*(?:"([A-Za-z0-9_.-]+)"|([A-Za-z_]\w*))',
            term,
        )
        if term_match is None:
            raise OperationSourceParseError(
                f"{label} {hasop_fn}() has an unsupported return term: {term!r}"
            )
        literal, identifier = term_match.groups()
        if literal:
            operation = literal
        elif identifier in constants:
            operation = constants[identifier]
        else:
            unresolved.append(identifier)
            continue
        if operation in operations:
            raise OperationSourceParseError(
                f"{label} {hasop_fn}() declares duplicate operation {operation!r}"
            )
        operations.add(operation)
    return frozenset(operations), tuple(sorted(set(unresolved)))


def _parse_direct_return_calls(
    native_job: str,
    function_name: str,
    suffix: str,
    argument_pattern: str,
) -> tuple[str, ...]:
    body = _function_body(native_job, "familyHasOp", "AriadneNativeJob.cpp")
    if function_name != "familyHasOp":
        body = _function_body(native_job, function_name, "AriadneNativeJob.cpp")
    body = _remove_supported_preprocessor_lines(body, "AriadneNativeJob.cpp")
    match = re.fullmatch(
        r"\s*(?:\(void\)\s*op\s*;\s*)?return\s+(.+?)\s*;\s*",
        body,
        flags=re.S,
    )
    if match is None:
        raise OperationSourceParseError(
            f"AriadneNativeJob.cpp {function_name}() is not one direct return expression"
        )
    calls: list[str] = []
    for term in match.group(1).split("||"):
        call_match = re.fullmatch(
            rf"([A-Za-z_]\w*{re.escape(suffix)})\s*\(\s*{argument_pattern}\s*\)",
            term.strip(),
        )
        if call_match is None:
            raise OperationSourceParseError(
                f"AriadneNativeJob.cpp {function_name}() has an unsupported return "
                f"term: {term.strip()!r}"
            )
        calls.append(call_match.group(1))
    if not calls or len(calls) != len(set(calls)):
        raise OperationSourceParseError(
            f"{function_name}() must contain non-empty unique family calls"
        )
    return tuple(calls)


def _parse_family_gate_calls(native_job: str) -> tuple[str, ...]:
    return _parse_direct_return_calls(
        native_job,
        "familyHasOp",
        "HasOp",
        r"op",
    )


def _parse_family_dispatch_calls(native_job: str) -> tuple[str, ...]:
    return _parse_direct_return_calls(
        native_job,
        "tryFamilyDispatch",
        "Dispatch",
        r"op\s*,\s*ctx\s*,\s*r",
    )


def _top_level_control_conditions(
    body: str,
    label: str,
) -> tuple[tuple[int, str, str, int], ...]:
    controls: list[tuple[int, str, str, int]] = []
    depth = 0
    state = "code"
    quote = ""
    index = 0
    while index < len(body):
        character = body[index]
        following = body[index + 1] if index + 1 < len(body) else ""
        if state == "string":
            if character == "\\" and following:
                index += 2
                continue
            if character == quote:
                state = "code"
            index += 1
            continue
        if character in {'"', "'"}:
            state = "string"
            quote = character
            index += 1
            continue
        if character == "{":
            depth += 1
            index += 1
            continue
        if character == "}":
            depth -= 1
            if depth < 0:
                raise OperationSourceParseError(f"{label} has an unmatched '}}'")
            index += 1
            continue
        if character.isalpha() or character == "_":
            end = index + 1
            while end < len(body) and (body[end].isalnum() or body[end] == "_"):
                end += 1
            word = body[index:end]
            if word in {"if", "switch", "while", "for"}:
                opening = end
                while opening < len(body) and body[opening].isspace():
                    opening += 1
                if opening >= len(body) or body[opening] != "(":
                    raise OperationSourceParseError(
                        f"{label} has unsupported top-level {word} syntax"
                    )
                closing = _matching_delimiter(
                    body, opening, "(", ")", f"{label} {word} condition"
                )
                controls.append((
                    depth,
                    word,
                    body[opening + 1 : closing].strip(),
                    closing,
                ))
                index = closing + 1
                continue
            index = end
            continue
        index += 1
    if depth != 0:
        raise OperationSourceParseError(f"{label} has unbalanced nested blocks")
    return tuple(controls)


def _is_exact_supported_handled_return(statement: str) -> bool:
    """Accept only the canonical successful bool terminals used by families."""

    normalized = statement.strip()
    return bool(
        re.fullmatch(r"return\s+true\s*;", normalized)
        or re.fullmatch(
            r"return\s+[A-Za-z_]\w*\s*\([^;]*\)\s*;",
            normalized,
        )
    )


def _require_direct_dispatch_branch_handles(
    body: str,
    condition_end: int,
    label: str,
) -> None:
    statement_start = condition_end + 1
    while statement_start < len(body) and body[statement_start].isspace():
        statement_start += 1
    if statement_start >= len(body):
        raise OperationSourceParseError(f"{label} has no handler statement")
    if body[statement_start] == "{":
        statement_end = _matching_delimiter(
            body,
            statement_start,
            "{",
            "}",
            f"{label} compound handler",
        )
        compound = body[statement_start + 1 : statement_end].rstrip()
        terminal = re.search(r"\breturn\s+[^;]+;\s*$", compound)
        if terminal is None or not _is_exact_supported_handled_return(
            terminal.group(0)
        ):
            raise OperationSourceParseError(
                f"{label} compound branch does not end in an exact supported "
                "handled return"
            )
        return
    semicolon = body.find(";", statement_start)
    if semicolon < 0:
        raise OperationSourceParseError(f"{label} direct handler has no terminator")
    statement = body[statement_start : semicolon + 1].strip()
    if not _is_exact_supported_handled_return(statement):
        raise OperationSourceParseError(
            f"{label} declines a declared operation or lacks an exact supported "
            f"handled return: {statement!r}"
        )


def _require_nonempty_legacy_dispatch_branch(
    body: str,
    condition_end: int,
    label: str,
) -> None:
    statement_start = condition_end + 1
    while statement_start < len(body) and body[statement_start].isspace():
        statement_start += 1
    if statement_start >= len(body) or body[statement_start] != "{":
        raise OperationSourceParseError(
            f"{label} must use a compound legacy dispatch branch"
        )
    statement_end = _matching_delimiter(
        body,
        statement_start,
        "{",
        "}",
        f"{label} legacy handler",
    )
    compound = body[statement_start + 1 : statement_end].strip()
    if not compound:
        raise OperationSourceParseError(f"{label} has an empty legacy dispatch branch")
    if re.fullmatch(r"if\s*\(\s*(?:false|0)\s*\)\s*\{.*\}", compound, re.S):
        raise OperationSourceParseError(
            f"{label} has an unreachable legacy dispatch branch"
        )


def _parse_m08l_overrule_helper_operations(
    text: str,
    label: str,
) -> frozenset[str]:
    helper_label = f"{label} m08lOverruleFor()"
    body = _function_body(text, "m08lOverruleFor", label)
    operations: set[str] = set()
    for depth, control, condition, condition_end in _top_level_control_conditions(
        body, helper_label
    ):
        if depth != 0 or re.search(r"\binstallOp\b", condition) is None:
            continue
        if control != "if":
            raise OperationSourceParseError(
                f"{helper_label} uses unsupported {control}(installOp) routing"
            )
        branch_operations: set[str] = set()
        for term in condition.split("||"):
            match = re.fullmatch(
                r'\s*installOp\s*==\s*"([A-Za-z0-9_.-]+)"\s*',
                term,
            )
            if match is None:
                raise OperationSourceParseError(
                    f"{helper_label} has unsupported operation condition {condition!r}"
                )
            branch_operations.add(match.group(1))
        _require_direct_dispatch_branch_handles(
            body, condition_end, helper_label
        )
        operations.update(branch_operations)
    if not operations:
        raise OperationSourceParseError(
            f"{helper_label} declares no supported install operations"
        )
    return frozenset(operations)


def _parse_op_comparison_expression(
    expression: str,
    constants: Mapping[str, str],
    label: str,
) -> frozenset[str]:
    operations: set[str] = set()
    for term in expression.split("||"):
        match = re.fullmatch(
            r'\s*op\s*==\s*(?:"([A-Za-z0-9_.-]+)"|([A-Za-z_]\w*))\s*',
            term,
        )
        if match is None:
            raise OperationSourceParseError(
                f"{label} has an unsupported operation dispatch condition: "
                f"{expression!r}"
            )
        literal, identifier = match.groups()
        if literal is not None:
            operation = literal
        elif identifier in constants:
            operation = constants[identifier]
        else:
            raise OperationSourceParseError(
                f"{label} references unresolved translation-unit constant "
                f"{identifier!r}"
            )
        operations.add(operation)
    return frozenset(operations)


def _parse_family_dispatch_operations(
    text: str,
    dispatch_fn: str,
    hasop_fn: str,
    admitted_operations: frozenset[str],
    label: str,
) -> frozenset[str]:
    body = _remove_supported_preprocessor_lines(
        _function_body(text, dispatch_fn, label),
        label,
    )
    constants = _translation_unit_string_constants(text, label)
    m08l_overrule_operations = (
        _parse_m08l_overrule_helper_operations(text, label)
        if label.endswith("m08l_handlers.inc")
        else frozenset()
    )
    operations: set[str] = set()
    noncanonical_m08d_operations: set[str] = set()
    for depth, control, condition, condition_end in _top_level_control_conditions(
        body, f"{label} {dispatch_fn}()"
    ):
        if re.fullmatch(r"(?:false|0)", condition):
            raise OperationSourceParseError(
                f"{label} {dispatch_fn}() contains an unreachable conditional branch"
            )
        masked_condition = _mask_cpp_string_literals(condition)
        if control == "if" and re.search(r"[A-Za-z_]", masked_condition) is None:
            raise OperationSourceParseError(
                f"{label} {dispatch_fn}() contains an unsupported outer guard: "
                f"{condition!r}"
            )
        if re.search(r"\bop\b", condition) is None:
            continue
        if depth > 0:
            if (
                label.endswith("m08l_handlers.inc")
                and re.fullmatch(
                    r'op\.rfind\("overrule\.",\s*0\)\s*==\s*0\s*&&\s*'
                    r'op\s*!=\s*"overrule\.global\.enable"\s*&&\s*'
                    r'op\s*!=\s*"overrule\.applicable"\s*&&\s*'
                    r'op\s*!=\s*"overrule\.query\.has"\s*&&\s*'
                    r'op\s*!=\s*"overrule\.remove"\s*&&\s*'
                    r'm08lOverruleFor\s*\(\s*op\s*,\s*pOv\s*,\s*pOvClass\s*,\s*className\s*\)',
                    condition,
                )
            ):
                operations.update(m08l_overrule_operations)
                _require_direct_dispatch_branch_handles(
                    body,
                    condition_end,
                    f"{label} {dispatch_fn}() overrule-helper branch",
                )
                continue
            if label.endswith("m08d_handlers.inc") and control == "if":
                try:
                    nested_operations = _parse_op_comparison_expression(
                        condition, constants, f"{label} {dispatch_fn}()"
                    )
                except OperationSourceParseError:
                    pass
                else:
                    if depth == 2:
                        operations.update(nested_operations)
                    else:
                        noncanonical_m08d_operations.update(nested_operations)
            continue
        if control == "if" and re.fullmatch(
            rf"!\s*{re.escape(hasop_fn)}\s*\(\s*op\s*\)", condition
        ):
            continue
        if control != "if":
            raise OperationSourceParseError(
                f"{label} {dispatch_fn}() uses unsupported {control}(op) dispatch"
            )
        if (
            label.endswith("m08n_handlers.inc")
            and re.fullmatch(r'op\.find\("editor\."\)\s*==\s*0', condition)
        ):
            operations.update(
                operation for operation in admitted_operations
                if operation.startswith("editor.")
            )
            _require_direct_dispatch_branch_handles(
                body,
                condition_end,
                f"{label} {dispatch_fn}() editor-prefix branch",
            )
            continue
        branch_operations = _parse_op_comparison_expression(
            condition, constants, f"{label} {dispatch_fn}()"
        )
        _require_direct_dispatch_branch_handles(
            body,
            condition_end,
            f"{label} {dispatch_fn}() operation branch",
        )
        operations.update(branch_operations)
    unsupported_nested_operations = noncanonical_m08d_operations - operations
    if unsupported_nested_operations:
        raise OperationSourceParseError(
            f"{label} {dispatch_fn}() has operation branches behind an "
            "unsupported outer guard: "
            f"{sorted(unsupported_nested_operations)!r}"
        )
    return frozenset(operations)


def _parse_legacy_dispatch_operations(
    native_job: str,
) -> frozenset[str]:
    label = "AriadneNativeJob.cpp ariadneNativeJobResult()"
    body = _remove_supported_preprocessor_lines(
        _function_body(
            native_job,
            "ariadneNativeJobResult",
            "AriadneNativeJob.cpp",
            return_type=r"std::string",
        ),
        "AriadneNativeJob.cpp",
    )
    constants = _translation_unit_string_constants(
        native_job, "AriadneNativeJob.cpp"
    )
    allowed_admission_checks = (
        r"!\s*isAriadneNativeOperationKnown\s*\(\s*op\s*\)",
        r"!\s*isAriadneNativeOperationAdmitted\s*\(\s*op\s*,\s*admissionScope\s*\)",
    )
    operations: set[str] = set()
    for depth, control, condition, condition_end in _top_level_control_conditions(body, label):
        if depth != 0:
            continue
        if re.search(r"\bop\b", condition) is None:
            continue
        if control == "if" and any(
            re.fullmatch(pattern, condition) for pattern in allowed_admission_checks
        ):
            continue
        if control != "if":
            raise OperationSourceParseError(
                f"{label} uses unsupported {control}(op) dispatch"
            )
        branch_operations = _parse_op_comparison_expression(
            condition, constants, label
        )
        _require_nonempty_legacy_dispatch_branch(body, condition_end, label)
        operations.update(branch_operations)
    if body.count("tryFamilyDispatch(op, ctx, r)") != 1:
        raise OperationSourceParseError(
            f"{label} must contain exactly one known family-dispatch seam"
        )
    return frozenset(operations)


def parse_native_sources(
    native_job_source: bytes,
    family_sources: Mapping[str, bytes],
) -> NativeSourceFacts:
    """Parse native dispatcher table and family gates from a byte snapshot."""

    native_job = _strip_cpp_comments(
        _decode_utf8(native_job_source, "AriadneNativeJob.cpp")
    )
    declared_family_includes = _native_operation_authority_includes(native_job)
    _validate_native_admission_contract(native_job)
    observed_family_includes = tuple(sorted(
        "families/" + PurePosixPath(relative_path).name
        for relative_path in family_sources
    ))
    if tuple(sorted(declared_family_includes)) != observed_family_includes:
        raise OperationSourceParseError(
            "native family source snapshot does not exactly match operation authority "
            f"includes; declared={declared_family_includes!r}; "
            f"observed={observed_family_includes!r}"
        )
    native_table, duplicate_native = _parse_operation_table(
        native_job,
        "kAriadneNativeOperationTable",
    )
    internal_table, duplicate_internal = _parse_operation_table(
        native_job,
        "kAriadneInternalOperationTable",
    )
    _validate_native_table_lookup_contract(native_job)

    runtime_gates = _parse_family_gate_calls(native_job)
    runtime_dispatchers = _parse_family_dispatch_calls(native_job)
    legacy_dispatch_operations = _parse_legacy_dispatch_operations(native_job)

    families: dict[str, NativeFamilyFacts] = {}
    for relative_path, source in sorted(family_sources.items()):
        file_name = PurePosixPath(relative_path).name
        spec = _family_spec(file_name)
        if spec is None:
            if file_name in _SUPPORTED_AUXILIARY_FAMILY_INCLUDES:
                continue
            raise OperationSourceParseError(
                f"unsupported captured native family source {relative_path!r}"
            )
        key, hasop_fn, label = spec
        operations, unresolved = parse_hasop_operations(
            source, hasop_fn, relative_path
        )
        dispatch_fn = hasop_fn.removesuffix("HasOp") + "Dispatch"
        family_text = _strip_cpp_comments(_decode_utf8(source, relative_path))
        _validate_family_preprocessor(family_text, relative_path)
        dispatch_operations = _parse_family_dispatch_operations(
            family_text,
            dispatch_fn,
            hasop_fn,
            operations,
            relative_path,
        )
        if key in families:
            raise OperationSourceParseError(
                f"duplicate native family key {key!r}"
            )
        families[key] = NativeFamilyFacts(
            key=key,
            file_name=file_name,
            hasop_fn=hasop_fn,
            label=label,
            operations=operations,
            dispatch_fn=dispatch_fn,
            dispatch_operations=dispatch_operations,
            unresolved=unresolved,
        )
    if not families:
        raise OperationSourceParseError("no native family modules were parsed")
    return NativeSourceFacts(
        families=families,
        runtime_family_gates=runtime_gates,
        runtime_family_dispatchers=runtime_dispatchers,
        legacy_dispatch_operations=legacy_dispatch_operations,
        native_table_operation_families=native_table,
        internal_table_operation_families=internal_table,
        duplicate_native_table_operations=duplicate_native,
        duplicate_internal_table_operations=duplicate_internal,
    )


def _module_scope_nodes(tree: ast.Module):
    """Walk nodes evaluated in module scope without entering nested scopes."""

    nested_scopes = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Lambda,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    def visit(node: ast.AST):
        for child in ast.iter_child_nodes(node):
            yield child
            if not isinstance(child, nested_scopes):
                yield from visit(child)

    yield from visit(tree)


def _module_scope_name_bindings(tree: ast.Module, name: str) -> tuple[ast.AST, ...]:
    bindings: list[ast.AST] = []
    for node in _module_scope_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                bindings.append(node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            if node.id == name:
                bindings.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                if bound_name == name:
                    bindings.append(node)
                    break
    return tuple(bindings)


def _require_single_module_function(
    tree: ast.Module,
    function_name: str,
    label: str,
) -> ast.FunctionDef:
    bindings = _module_scope_name_bindings(tree, function_name)
    direct_functions = [
        statement for statement in tree.body
        if isinstance(statement, ast.FunctionDef)
        and statement.name == function_name
    ]
    if len(bindings) != 1 or len(direct_functions) != 1:
        raise OperationSourceParseError(
            f"{label}.{function_name} must be one top-level function and cannot "
            "be rebound"
        )
    return direct_functions[0]


def _reject_module_attribute_rebindings(
    tree: ast.Module,
    module_names: tuple[str, ...],
    label: str,
) -> None:
    critical_attributes = frozenset({"WRITE_OP_MAP", "build_job_args", "ir_op_for"})
    rebound: set[str] = set()
    for node in _module_scope_nodes(tree):
        if not (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Name)
            and node.value.id in module_names
            and node.attr in critical_attributes
        ):
            continue
        rebound.add(f"{node.value.id}.{node.attr}")
    if rebound:
        raise OperationSourceParseError(
            f"{label} critical family module attributes cannot be rebound: "
            f"{sorted(rebound)!r}"
        )


def _assignment_value(tree: ast.Module, variable_name: str, label: str) -> ast.expr:
    matches: list[ast.expr] = []
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.target.id == variable_name:
                if statement.value is not None:
                    matches.append(statement.value)
        elif isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == variable_name
                for target in statement.targets
            ):
                matches.append(statement.value)
    if len(matches) != 1:
        raise OperationSourceParseError(
            f"{label} must define {variable_name} exactly once"
        )
    return matches[0]


def _parse_python(source: bytes, label: str) -> ast.Module:
    text = _decode_utf8(source, label)
    try:
        return ast.parse(text, filename=label)
    except SyntaxError as exc:
        raise OperationSourceParseError(f"{label} has invalid Python syntax: {exc}") from exc


def parse_literal_string_map(
    source: bytes,
    variable_name: str,
    label: str,
) -> dict[str, str]:
    """Extract one literal string-to-string dict without executing Python."""

    value = _assignment_value(_parse_python(source, label), variable_name, label)
    try:
        result = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise OperationSourceParseError(
            f"{label}.{variable_name} is not a literal dict: {exc}"
        ) from exc
    if not isinstance(result, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in result.items()
    ):
        raise OperationSourceParseError(
            f"{label}.{variable_name} must be a string-to-string dict"
        )
    return dict(result)


def _native_write_map_module_names(tree: ast.Module, label: str) -> tuple[str, ...]:
    label = "tools/patch_ops/__init__.py"
    value = _assignment_value(
        tree, "NATIVE_WRITE_OP_MAP", label
    )
    if not isinstance(value, ast.Dict):
        raise OperationSourceParseError(
            f"{label}.NATIVE_WRITE_OP_MAP must be a dict aggregate"
        )
    modules: list[str] = []
    for key, item in zip(value.keys, value.values):
        if key is not None:
            raise OperationSourceParseError(
                f"{label}.NATIVE_WRITE_OP_MAP must aggregate WRITE_OP_MAP values"
            )
        if not (
            isinstance(item, ast.Attribute)
            and item.attr == "WRITE_OP_MAP"
            and isinstance(item.value, ast.Name)
        ):
            raise OperationSourceParseError(
                f"{label}.NATIVE_WRITE_OP_MAP has an unsupported aggregate entry"
            )
        modules.append(item.value.id)
    if not modules or len(modules) != len(set(modules)):
        raise OperationSourceParseError(
            f"{label}.NATIVE_WRITE_OP_MAP has empty or duplicate modules"
        )
    return tuple(modules)


def discover_patch_family_module_names(patch_ops_init: bytes) -> tuple[str, ...]:
    """Discover aggregate source paths without importing or enforcing bindings."""

    label = "tools/patch_ops/__init__.py"
    return _native_write_map_module_names(_parse_python(patch_ops_init, label), label)


def _validate_patch_aggregate_build_job_args(tree: ast.Module, label: str) -> None:
    function = _require_single_module_function(tree, "build_job_args", label)
    statements = list(function.body)
    if statements and isinstance(statements[0], ast.Expr) and isinstance(
        statements[0].value, ast.Constant
    ) and isinstance(statements[0].value.value, str):
        statements.pop(0)
    valid = (
        not function.decorator_list
        and [argument.arg for argument in function.args.args] == ["native_op", "args"]
        and len(statements) == 2
        and isinstance(statements[0], ast.For)
        and isinstance(statements[0].target, ast.Name)
        and statements[0].target.id == "fam"
        and isinstance(statements[0].iter, ast.Name)
        and statements[0].iter.id == "_FAMILIES"
        and not statements[0].orelse
        and len(statements[0].body) == 2
        and isinstance(statements[0].body[0], ast.Assign)
        and len(statements[0].body[0].targets) == 1
        and isinstance(statements[0].body[0].targets[0], ast.Name)
        and statements[0].body[0].targets[0].id == "result"
        and isinstance(statements[0].body[0].value, ast.Call)
        and isinstance(statements[0].body[0].value.func, ast.Attribute)
        and isinstance(statements[0].body[0].value.func.value, ast.Name)
        and statements[0].body[0].value.func.value.id == "fam"
        and statements[0].body[0].value.func.attr == "build_job_args"
        and [
            argument.id
            for argument in statements[0].body[0].value.args
            if isinstance(argument, ast.Name)
        ] == ["native_op", "args"]
        and len(statements[0].body[0].value.args) == 2
        and not statements[0].body[0].value.keywords
        and isinstance(statements[0].body[1], ast.If)
        and not statements[0].body[1].orelse
        and isinstance(statements[0].body[1].test, ast.Compare)
        and isinstance(statements[0].body[1].test.left, ast.Name)
        and statements[0].body[1].test.left.id == "result"
        and len(statements[0].body[1].test.ops) == 1
        and isinstance(statements[0].body[1].test.ops[0], ast.IsNot)
        and len(statements[0].body[1].test.comparators) == 1
        and isinstance(statements[0].body[1].test.comparators[0], ast.Constant)
        and statements[0].body[1].test.comparators[0].value is None
        and len(statements[0].body[1].body) == 1
        and isinstance(statements[0].body[1].body[0], ast.Return)
        and isinstance(statements[0].body[1].body[0].value, ast.Name)
        and statements[0].body[1].body[0].value.id == "result"
        and isinstance(statements[1], ast.Return)
        and isinstance(statements[1].value, ast.Dict)
        and not statements[1].value.keys
        and not statements[1].value.values
    )
    if not valid:
        raise OperationSourceParseError(
            f"{label} aggregate build_job_args must iterate _FAMILIES, call each "
            "fam.build_job_args(native_op, args), return the first non-None "
            "result, and otherwise return {}"
        )


def patch_family_module_names(patch_ops_init: bytes) -> tuple[str, ...]:
    """Validate the exact patch aggregate contract without importing it."""

    label = "tools/patch_ops/__init__.py"
    tree = _parse_python(patch_ops_init, label)
    map_modules = _native_write_map_module_names(tree, label)

    all_relative_imports = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    ]
    top_level_relative_imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.level > 0
    ]
    if len(all_relative_imports) != len(top_level_relative_imports):
        raise OperationSourceParseError(
            f"{label} relative imports must be top-level"
        )
    if len(top_level_relative_imports) != 1:
        raise OperationSourceParseError(
            f"{label} must have exactly one top-level relative imports statement"
        )
    relative_import = top_level_relative_imports[0]
    if relative_import.level != 1 or relative_import.module is not None:
        raise OperationSourceParseError(
            f"{label} relative imports must use exact 'from . import ...' syntax"
        )
    if any(alias.asname is not None for alias in relative_import.names):
        raise OperationSourceParseError(
            f"{label} relative import aliases are unsupported"
        )
    import_modules = tuple(alias.name for alias in relative_import.names)
    if len(import_modules) != len(set(import_modules)):
        raise OperationSourceParseError(
            f"{label} relative imports contain duplicate module bindings"
        )
    if set(import_modules) != set(map_modules):
        raise OperationSourceParseError(
            f"{label} relative imports must bind exactly the NATIVE_WRITE_OP_MAP "
            f"modules; imports={import_modules!r}; map={map_modules!r}"
        )

    family_value = _assignment_value(tree, "_FAMILIES", label)
    if not isinstance(family_value, ast.Tuple) or not all(
        isinstance(item, ast.Name) for item in family_value.elts
    ):
        raise OperationSourceParseError(
            f"{label}._FAMILIES must be a literal tuple of module names"
        )
    family_modules = tuple(item.id for item in family_value.elts)
    if not family_modules or len(family_modules) != len(set(family_modules)):
        raise OperationSourceParseError(
            f"{label}._FAMILIES must contain non-empty unique module names"
        )
    if family_modules != map_modules:
        raise OperationSourceParseError(
            f"{label}._FAMILIES must exactly match NATIVE_WRITE_OP_MAP order; "
            f"families={family_modules!r}; map={map_modules!r}"
        )
    _reject_module_attribute_rebindings(tree, map_modules, label)
    _validate_patch_aggregate_build_job_args(tree, label)
    return map_modules


def _build_job_args_operation_branches(
    source: bytes,
    label: str,
) -> frozenset[str]:
    tree = _parse_python(source, label)
    function = _require_single_module_function(tree, "build_job_args", label)
    if function.decorator_list or [arg.arg for arg in function.args.args] != [
        "native_op",
        "args",
    ]:
        raise OperationSourceParseError(
            f"{label}.build_job_args has an unsupported signature"
        )
    statements = list(function.body)
    if statements and isinstance(statements[0], ast.Expr) and isinstance(
        statements[0].value, ast.Constant
    ) and isinstance(statements[0].value.value, str):
        statements.pop(0)
    if not statements or not isinstance(statements[-1], ast.Return) or not (
        statements[-1].value is None
        or (
            isinstance(statements[-1].value, ast.Constant)
            and statements[-1].value.value is None
        )
    ):
        raise OperationSourceParseError(
            f"{label}.build_job_args must end with direct return None"
        )

    operations: set[str] = set()
    for statement in statements[:-1]:
        if not isinstance(statement, ast.If) or statement.orelse:
            raise OperationSourceParseError(
                f"{label}.build_job_args supports only top-level independent if branches"
            )
        test = statement.test
        branch_operations: tuple[str, ...]
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "native_op"
            and len(test.ops) == 1
            and len(test.comparators) == 1
            and isinstance(test.ops[0], ast.Eq)
            and isinstance(test.comparators[0], ast.Constant)
            and isinstance(test.comparators[0].value, str)
        ):
            branch_operations = (test.comparators[0].value,)
        elif (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "native_op"
            and len(test.ops) == 1
            and len(test.comparators) == 1
            and isinstance(test.ops[0], ast.In)
            and isinstance(test.comparators[0], ast.Tuple)
            and all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in test.comparators[0].elts
            )
        ):
            branch_operations = tuple(
                item.value for item in test.comparators[0].elts
            )
        else:
            raise OperationSourceParseError(
                f"{label}.build_job_args has an unsupported native_op branch"
            )
        if not branch_operations or len(branch_operations) != len(set(branch_operations)):
            raise OperationSourceParseError(
                f"{label}.build_job_args has an empty or duplicate membership branch"
            )
        if not statement.body or not isinstance(statement.body[-1], ast.Return):
            raise OperationSourceParseError(
                f"{label}.build_job_args branch does not end in a direct return"
            )
        terminal = statement.body[-1].value
        if terminal is None or (
            isinstance(terminal, ast.Constant) and terminal.value is None
        ):
            raise OperationSourceParseError(
                f"{label}.build_job_args branch returns None instead of handling"
            )
        overlap = operations.intersection(branch_operations)
        if overlap:
            raise OperationSourceParseError(
                f"{label}.build_job_args has duplicate native_op branches: "
                f"{sorted(overlap)!r}"
            )
        operations.update(branch_operations)
    return frozenset(operations)


def parse_patch_vocabularies(
    patch_engine_source: bytes,
    patch_ops_init: bytes,
    patch_family_sources: Mapping[str, bytes],
) -> dict[str, dict[str, str]]:
    """Parse declared and live patch vocabularies from one byte snapshot."""

    declared = parse_literal_string_map(
        patch_engine_source,
        "OP_REGISTRY_MAP",
        "tools/patch_engine.py",
    )
    native: dict[str, str] = {}
    for module_name in patch_family_module_names(patch_ops_init):
        label = f"tools/patch_ops/{module_name}.py"
        try:
            source = patch_family_sources[module_name]
        except KeyError as exc:
            raise OperationSourceParseError(f"missing patch family source: {label}") from exc
        family_map = parse_literal_string_map(source, "WRITE_OP_MAP", label)
        mapped_operations = frozenset(family_map.values())
        dispatched_operations = _build_job_args_operation_branches(source, label)
        if mapped_operations != dispatched_operations:
            raise PatchFamilyDispatchMismatch(
                f"{label} WRITE_OP_MAP/build_job_args mismatch: "
                f"map-only={sorted(mapped_operations - dispatched_operations)!r}; "
                f"dispatch-only={sorted(dispatched_operations - mapped_operations)!r}"
            )
        overlap = set(native).intersection(family_map)
        if overlap:
            raise OperationSourceParseError(
                f"duplicate patch operation ids across families: {sorted(overlap)!r}"
            )
        native.update(family_map)
    return {
        "patch_engine.OP_REGISTRY_MAP": declared,
        "patch_ops.NATIVE_WRITE_OP_MAP": native,
    }


def check_vocab_lockstep(
    registry: Mapping[str, object],
    coded_operations: frozenset[str] | set[str],
    external_vocab: Mapping[str, Mapping[str, str]],
) -> list[dict[str, str]]:
    """Cross-check patch targets against registry and native live gates."""

    operations = registry.get("operations", [])
    by_id = {
        operation.get("id"): operation
        for operation in operations
        if isinstance(operation, dict) and isinstance(operation.get("id"), str)
    }
    violations: list[dict[str, str]] = []
    for surface in sorted(external_vocab):
        mapping = external_vocab[surface]
        for patch_op in sorted(mapping):
            registry_id = mapping[patch_op]
            base = {"surface": surface, "patch_op": patch_op, "target": registry_id}
            record = by_id.get(registry_id)
            if record is None:
                violations.append(
                    dict(
                        base,
                        problem="dangling_target",
                        detail=f"{registry_id!r} is not a registry op-id",
                    )
                )
                continue
            if registry_id not in coded_operations:
                violations.append(
                    dict(
                        base,
                        problem="no_live_hasop",
                        detail=f"{registry_id!r} is not admitted by the native dispatcher",
                    )
                )
            if record.get("status") != "implemented":
                violations.append(
                    dict(
                        base,
                        problem="not_implemented",
                        detail=f"registry status={record.get('status')!r}",
                    )
                )
            if not record.get("evidence_refs"):
                violations.append(
                    dict(
                        base,
                        problem="missing_evidence_ref",
                        detail="evidence_refs is empty/absent",
                    )
                )
    return violations
