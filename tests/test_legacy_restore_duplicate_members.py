"""Legacy imports must not restore the same path twice and overwrite its backup."""
import warnings
import zipfile

import pytest

import data_paths


@pytest.mark.parametrize("duplicate", ["seat_names.json", "config/PTZ1IP.txt"])
def test_legacy_duplicate_rejected_before_any_write(tmp_path, monkeypatch, duplicate):
    data = tmp_path / "data"
    app = tmp_path / "app"
    data.mkdir()
    app.mkdir()
    monkeypatch.setattr(data_paths, "CONFIG_DIR", data)
    target = data / "seat_names.json" if duplicate.endswith(".json") else app / "PTZ1IP.txt"
    target.write_bytes(b"original")
    target.with_suffix(".bak").write_bytes(b"previous recovery")
    archive = tmp_path / "duplicate.zip"
    payload = '{"synthetic": true}' if duplicate.endswith(".json") else "synthetic-endpoint"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(duplicate, payload)
            zf.writestr(duplicate, payload)

    with pytest.raises(ValueError, match="[Dd]uplic"):
        data_paths.import_backup(archive, app_dir=app)

    assert target.read_bytes() == b"original"
    assert target.with_suffix(".bak").read_bytes() == b"previous recovery"
