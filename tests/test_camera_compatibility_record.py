"""Keep the blank compatibility record distinct from a tested runtime profile."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_template_claims_no_model_hardware_or_review():
    record = json.loads((ROOT / 'config/examples/camera-compatibility-template.json').read_text())
    assert record['record_kind'] == 'compatibility-evidence-only-not-runtime-config'
    assert record['status'] == 'unverified'
    for key in ('manufacturer', 'model', 'firmware', 'transport', 'port', 'independent_review'):
        assert record[key] is None
    assert set(record['checks'].values()) == {'not-tested'}
    assert record['hardware_evidence'] == []


def test_runtime_loader_does_not_consume_evidence_template():
    assert 'camera-compatibility-template' not in (ROOT / 'config/loader.py').read_text()
