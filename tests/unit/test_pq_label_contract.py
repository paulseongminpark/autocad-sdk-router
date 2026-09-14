"""PQ additions must reuse the public runner and fail before CAD on invalid input."""
import hashlib
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from cadctl import Cad


def test_registry_and_build_contract():
    registry = json.loads((ROOT / 'config/operations.v2.json').read_text(encoding='utf-8-sig'))
    schemas = json.loads((ROOT / 'schemas/pq_label.args.schema.json').read_text())['$defs']
    records = [o for o in registry['operations'] if o['family'] == 'pq_label']
    assert {o['id'][9:] for o in records} == set(schemas)
    for record in records:
        assert record['args_schema'] == schemas[record['id'][9:]]
        assert record['handler']['router_lane'] == 'PQ_LABEL_JOB'
        assert record['write_level']['allowed_write_modes'] in [['read'], ['write_copy']]
        jsonschema.Draft7Validator.check_schema(record['args_schema'])
    manifest = json.loads((ROOT / 'prebuilt/2027/pq-label/router/manifest.json').read_text(encoding='utf-8-sig'))
    assert hashlib.sha256((ROOT / 'prebuilt/2027/pq-label/router/PqLabel.dll').read_bytes()).hexdigest().upper() == manifest['sha256']
    for path, expected in manifest['sources'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper() == expected


@pytest.mark.parametrize('args', [
    {}, {'handles': []}, {'handles': ['ZZ'], 'class_id': 'WALL', 'class_kind': 'STUFF'},
    {'handles': ['AB'], 'class_id': 'WALL', 'class_kind': 'OTHER'},
    {'handles': ['AB'], 'class_id': 'WALL', 'class_kind': 'STUFF', 'layer': 'A-WALL'},
    {'handles': ['AB'], 'class_id': 'WALL', 'class_kind': 'STUFF', 'overwrite': 'yes'},
])
def test_invalid_arguments_do_not_launch_cad(tmp_path, monkeypatch, args):
    import run_job
    monkeypatch.setattr(run_job, 'run_router_cad_job', lambda *a, **k: pytest.fail('CAD launched'))
    result = Cad().run_operation('pq_label.class.set', args=args,
                                dwg_path=str(tmp_path/'missing.dwg'), out_dir=str(tmp_path/'out'))
    assert result['executed'] is False
    assert 'INVALID_OPERATION_ARGUMENTS' in result['reason']


def test_original_write_is_refused(tmp_path):
    result = Cad().run_operation('pq_label.class.set', write_mode='write_original', out_dir=str(tmp_path))
    assert result['executed'] is False


def test_mcp_surface_stays_shared():
    import cadagent_mcp
    assert 'cad.query_entities' in cadagent_mcp._DISPATCH
    assert 'cad.run_operation' in cadagent_mcp._DISPATCH
    assert not any(name.startswith('pq_label.') for name in cadagent_mcp._DISPATCH)


def test_pq_arguments_are_discoverable_in_registry_and_dag():
    from op_dag_generate import build_dag
    record = Cad().registry_explain('pq_label.class.set')['record']
    node = next(n for n in build_dag()['nodes'] if n['op_id'] == record['id'])
    assert node['arg_keys'] == sorted(record['args_schema']['properties'])
