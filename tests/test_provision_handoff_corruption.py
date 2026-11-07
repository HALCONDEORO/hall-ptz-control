"""A damaged installer result must neither crash polling nor claim success."""
import json

import pytest

from application.provision_handoff import ProvisionHandoff


@pytest.mark.parametrize('payload', [
    None, [], True, 'bad', 17, {},
    {'ok': 'false'}, {'ok': 'true'}, {'ok': 1}, {'ok': None},
    {'ok': True, 'written': None}, {'ok': True, 'written': 'config.yaml'},
    {'ok': True, 'written': [None]},
    {'ok': False, 'issues': None}, {'ok': False, 'issues': [None]},
    {'ok': False, 'issues': ['bad']},
    {'ok': False, 'issues': [{'message': []}]},
    {'ok': False, 'error': []},
])
def test_damaged_result_is_a_safe_failure(tmp_path, payload):
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    result = ProvisionHandoff(tmp_path / 'request.json', path).poll()
    assert result is not None
    assert result.ok is False
    assert 'unreadable result' in result.error
    assert 'failed' in result.summary().lower()


def test_invalid_utf8_result_is_a_safe_failure(tmp_path):
    path = tmp_path / 'result.json'
    path.write_bytes(b'\xff\xfe\x80')
    result = ProvisionHandoff(tmp_path / 'request.json', path).poll()
    assert result is not None and not result.ok
    assert 'unreadable result' in result.error
    assert result.summary()
