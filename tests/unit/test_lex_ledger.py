import re
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parents[2] / "docs" / "LEX_LEDGER.md"

REQUIRED_IDS = [f"LEX-{n:04d}" for n in range(1, 6)]
REQUIRED_LABELS = ["observation", "rule", "substitute_verifier", "status", "refs"]
ALLOWED_STATUSES = {"candidate", "legislated", "rejected", "retracted"}


def _read_ledger():
    return LEDGER_PATH.read_text(encoding="utf-8")


def _entry_blocks(text):
    sentinel = "__END__"
    ids = REQUIRED_IDS + [sentinel]
    blocks = {}
    for entry_id, next_id in zip(REQUIRED_IDS, ids[1:]):
        start = text.index(f"[{entry_id}]")
        end = text.index(f"[{next_id}]") if next_id != sentinel else len(text)
        blocks[entry_id] = text[start:end]
    return blocks


def test_all_ids_present():
    text = _read_ledger()
    for entry_id in REQUIRED_IDS:
        assert f"[{entry_id}]" in text, f"missing entry id {entry_id}"


def test_every_entry_has_required_labels():
    text = _read_ledger()
    blocks = _entry_blocks(text)
    for entry_id, block in blocks.items():
        for label in REQUIRED_LABELS:
            assert re.search(rf"\b{label}\b", block), (
                f"{entry_id} missing label '{label}'"
            )


def test_status_values_are_allowed():
    text = _read_ledger()
    blocks = _entry_blocks(text)
    for entry_id, block in blocks.items():
        match = re.search(r"\bstatus\b[*:\s]*:?\s*([a-zA-Z_]+)", block)
        assert match, f"{entry_id} has no parsable status value"
        status = match.group(1).strip().rstrip("*")
        assert status in ALLOWED_STATUSES, (
            f"{entry_id} has disallowed status value: {status!r}"
        )


def test_lex_0005_is_rejected():
    text = _read_ledger()
    blocks = _entry_blocks(text)
    block = blocks["LEX-0005"]
    match = re.search(r"\bstatus\b[*:\s]*:?\s*([a-zA-Z_]+)", block)
    assert match, "LEX-0005 has no parsable status value"
    assert match.group(1).strip().rstrip("*") == "rejected"
