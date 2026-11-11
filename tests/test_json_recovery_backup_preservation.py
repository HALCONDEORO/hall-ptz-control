"""Saving recovered data must not replace a good .bak with corrupt bytes."""
import json

import pytest

from core.json_io import load_json, save_json


@pytest.mark.parametrize('corrupt', [b'{broken', b'\xff\xfe'])
@pytest.mark.parametrize('fail_replace', [False, True])
def test_save_after_recovery_keeps_valid_backup(tmp_path, monkeypatch, corrupt, fail_replace):
    primary = tmp_path / 'seat_names.json'
    backup = primary.with_suffix('.bak')
    good_bytes = b'{"seat": "last recoverable name"}'
    backup.write_bytes(good_bytes)
    primary.write_bytes(corrupt)
    recovered = load_json(primary, default={})
    assert recovered == json.loads(good_bytes)
    recovered['new-seat'] = 'edited name'
    if fail_replace:
        def denied(*args, **kwargs):
            raise PermissionError('synthetic replacement failure')
        monkeypatch.setattr('core.json_io.os.replace', denied)
    assert save_json(primary, recovered) is not fail_replace
    assert backup.read_bytes() == good_bytes
    if fail_replace:
        assert primary.read_bytes() == corrupt
        assert load_json(primary, default={}) == json.loads(good_bytes)
    else:
        assert load_json(primary) == recovered
    assert not list(tmp_path.glob('.tmp_*.json'))
