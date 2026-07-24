"""External dataset label vocabulary mapping.

The dataset vocabularies are deliberately exact-match only; revise FORMAT_SPEC and
the shipped map after validating real downloads.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


# Single revision point for the offline label-map file format.
FORMAT_SPEC = {
    "map_version": "lm.v1",
    "map_key": "map",
    "sets_key": "sets",
    "unmapped_policy_key": "unmapped_policy",
    "entry_keys": {"label": "label", "confidence": "confidence"},
    "target_labels": {"wall", "opening", "other"},
    "confidences": {"known", "assumed"},
    "class_matching": "exact",
}

_MAP_PATH = Path(__file__).resolve().parents[3] / "reports" / "e2" / "s3" / "label_map.json"


class _MappingDict(dict):
    """dict retaining duplicate JSON keys for validation."""

    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        super().__init__()
        self.duplicate_keys: list[str] = []
        for key, value in pairs:
            if key in self:
                self.duplicate_keys.append(key)
            self[key] = value


def _mapping_dict(pairs: list[tuple[str, Any]]) -> _MappingDict:
    return _MappingDict(pairs)


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Load the shipped label map, retaining any duplicate JSON keys."""
    map_path = Path(path) if path is not None else _MAP_PATH
    with map_path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_mapping_dict)


def to_label(set_name: str, cls: str) -> str:
    """Return a canonical label; unknown sets/invalid entries remain ``unknown``."""
    mapping = load()
    sets = mapping.get(FORMAT_SPEC["sets_key"])
    if not isinstance(sets, dict) or set_name not in sets:
        return "unknown"
    classes = sets[set_name]
    if not isinstance(classes, dict):
        return "unknown"
    entry = classes.get(cls)
    if entry is None:
        policy = mapping.get(FORMAT_SPEC["unmapped_policy_key"])
        return policy if policy in FORMAT_SPEC["target_labels"] else "unknown"
    if not isinstance(entry, dict):
        return "unknown"
    label = entry.get(FORMAT_SPEC["entry_keys"]["label"])
    return label if label in FORMAT_SPEC["target_labels"] else "unknown"


def _duplicate_violations(value: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, _MappingDict):
        for key in value.duplicate_keys:
            violations.append(f"duplicate key: {path}.{key}")
    if isinstance(value, dict):
        for key, nested in value.items():
            violations.extend(_duplicate_violations(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            violations.extend(_duplicate_violations(nested, f"{path}[{index}]"))
    return violations


def validate(mapping: dict[str, Any]) -> list[str]:
    """Return format violations, including target labels, duplicate keys, and empty sets."""
    violations = _duplicate_violations(mapping)
    sets_key = FORMAT_SPEC["sets_key"]
    label_key = FORMAT_SPEC["entry_keys"]["label"]
    confidence_key = FORMAT_SPEC["entry_keys"]["confidence"]

    if mapping.get(FORMAT_SPEC["map_key"]) != FORMAT_SPEC["map_version"]:
        violations.append("unknown map version")
    if mapping.get(FORMAT_SPEC["unmapped_policy_key"]) not in FORMAT_SPEC["target_labels"]:
        violations.append("unknown unmapped policy")

    sets = mapping.get(sets_key)
    if not isinstance(sets, dict) or not sets:
        violations.append("empty sets")
        return violations

    for set_name, classes in sets.items():
        if not isinstance(classes, dict) or not classes:
            violations.append(f"empty set: {set_name}")
            continue
        for cls, entry in classes.items():
            if not isinstance(entry, dict):
                violations.append(f"invalid entry: {set_name}.{cls}")
                continue
            if entry.get(label_key) not in FORMAT_SPEC["target_labels"]:
                violations.append(f"unknown target label: {set_name}.{cls}")
            if entry.get(confidence_key) not in FORMAT_SPEC["confidences"]:
                violations.append(f"unknown confidence: {set_name}.{cls}")
    return violations


def _selftest() -> None:
    shipped = load()
    assert validate(shipped) == []

    cases = {
        ("floorplancad", "wall"): "wall",
        ("floorplancad", "interior-wall"): "wall",
        ("floorplancad", "door"): "opening",
        ("floorplancad", "window"): "opening",
        ("floorplancad", "room"): "other",
        ("floorplancad", "not-in-map"): "other",
        ("cubicasa", "Wall"): "wall",
        ("cubicasa", "Door"): "opening",
        ("cubicasa", "Window"): "opening",
        ("cubicasa", "FixedFurniture"): "other",
        ("cubicasa", "not-in-map"): "other",
        ("not-a-set", "Wall"): "unknown",
    }
    for (set_name, cls), expected in cases.items():
        assert to_label(set_name, cls) == expected

    with tempfile.TemporaryDirectory() as temp_dir:
        fixture_path = Path(temp_dir) / "label_map_fixture.json"
        fixture = {
            FORMAT_SPEC["map_key"]: FORMAT_SPEC["map_version"],
            FORMAT_SPEC["sets_key"]: {
                "fixture": {
                    "sample": {
                        FORMAT_SPEC["entry_keys"]["label"]: "wall",
                        FORMAT_SPEC["entry_keys"]["confidence"]: "assumed",
                    }
                }
            },
            FORMAT_SPEC["unmapped_policy_key"]: "other",
        }
        fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
        assert validate(load(fixture_path)) == []
        fixture_path.write_text(
            '{"map":"lm.v1","sets":{"fixture":{"sample":'
            '{"label":"wall","label":"other","confidence":"assumed"}}},'
            '"unmapped_policy":"other"}',
            encoding="utf-8",
        )
        assert any("duplicate key" in item for item in validate(load(fixture_path)))

    print("selftest: shipped label map validation: 0 violations")
    print(f"selftest: {len(cases)} label lookups passed")
    print("selftest: temporary FORMAT_SPEC fixture and duplicate-key check passed")
    print("PASS_WITH_DEFERRAL: real dataset vocabularies require offline-download validation")


if __name__ == "__main__":
    if "--selftest" not in sys.argv:
        raise SystemExit("usage: label_map.py --selftest")
    _selftest()
