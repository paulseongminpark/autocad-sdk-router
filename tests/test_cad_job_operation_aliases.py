import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "cad_job.schema.json"
CATALOG = ROOT / "config" / "autocad_native_arx_operation_catalog.json"
ALIAS_MAP = ROOT / "config" / "cad_job_operation_aliases.json"

REQUIRED_FIELDS = {
    "operation",
    "catalog_op_id",
    "phase_batch",
    "execution_host_class",
    "mapping_type",
    "is_router_alias_or_synthetic",
}
HOST_CLASSES = {"coreconsole", "full_autocad", "dbx", "arx_adapter"}
MAPPING_TYPES = {"exact", "alias", "synthetic"}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def schema_operations():
    schema = load_json(SCHEMA)
    return schema["properties"]["operation"]["enum"]


def catalog_operation_ids():
    catalog = load_json(CATALOG)
    return {operation["op_id"] for operation in catalog["operations"]}


def alias_entries():
    alias_map = load_json(ALIAS_MAP)
    assert alias_map["schema"] == "ariadne.cad_job_operation_aliases.v1"
    assert isinstance(alias_map["operations"], dict)
    return alias_map["operations"]


def test_every_schema_operation_is_present_in_alias_map():
    assert set(alias_entries()) == set(schema_operations())


def test_every_alias_mapping_has_required_fields():
    for operation, entry in alias_entries().items():
        assert set(entry) >= REQUIRED_FIELDS, operation
        assert entry["operation"] == operation
        assert entry["execution_host_class"] in HOST_CLASSES
        assert entry["mapping_type"] in MAPPING_TYPES
        assert isinstance(entry["phase_batch"], str)
        assert entry["phase_batch"].strip()
        assert isinstance(entry["is_router_alias_or_synthetic"], bool)


def test_exact_catalog_ids_really_exist_in_catalog():
    catalog_ids = catalog_operation_ids()

    for operation, entry in alias_entries().items():
        if entry["mapping_type"] == "exact":
            assert entry["catalog_op_id"] == operation
            assert entry["catalog_op_id"] in catalog_ids
            assert entry["is_router_alias_or_synthetic"] is False


def test_alias_or_synthetic_operations_are_not_silent_catalog_ids():
    catalog_ids = catalog_operation_ids()

    for operation, entry in alias_entries().items():
        if operation in catalog_ids:
            assert entry["mapping_type"] == "exact"
            assert entry["catalog_op_id"] == operation
            continue

        assert entry["mapping_type"] in {"alias", "synthetic"}, operation
        assert entry["catalog_op_id"] is None
        assert entry["is_router_alias_or_synthetic"] is True
        assert entry.get("notes", "").strip()
        for catalog_ref in entry.get("catalog_reference_ids", []):
            assert catalog_ref in catalog_ids
