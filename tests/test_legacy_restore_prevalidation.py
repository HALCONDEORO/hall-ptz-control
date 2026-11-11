"""Reject malformed later entries before an earlier member changes runtime data."""
import json
import zipfile

import pytest

import data_paths


@pytest.mark.parametrize("invalid_name,payload,error", [
    ("schedule.json", b"not JSON", json.JSONDecodeError),
    ("schedule.json", b"[]", ValueError),
    ("schedule.json", b"\xff", UnicodeDecodeError),
    ("config/PTZ1IP.txt", b"\xff", UnicodeDecodeError),
])
def test_legacy_prevalidates_all_payloads_before_first_write(tmp_path, monkeypatch, invalid_name, payload, error):
    data = tmp_path / "data"
    app = tmp_path / "app"
    data.mkdir()
    app.mkdir()
    monkeypatch.setattr(data_paths, "CONFIG_DIR", data)
    current = data / "seat_names.json"
    current.write_bytes(b'{"original": true}')
    current.with_suffix(".bak").write_bytes(b"previous recovery")
    archive = tmp_path / "invalid-later-entry.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("seat_names.json", '{"replacement": true}')
        zf.writestr(invalid_name, payload)

    with pytest.raises(error):
        data_paths.import_backup(archive, app_dir=app)

    assert current.read_bytes() == b'{"original": true}'
    assert current.with_suffix(".bak").read_bytes() == b"previous recovery"
    assert not (data / "schedule.json").exists()
    assert list(app.iterdir()) == []
