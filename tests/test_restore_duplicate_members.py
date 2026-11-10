"""A restore archive must have a single unambiguous value per member name."""
import json
import warnings
import zipfile
from unittest.mock import Mock

import pytest

from application.restore_service import RestoreError, RestoreService


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("duplicate", ["manifest.json", "config.yaml", "seat_names.json"])
def test_duplicate_archive_member_rejected_before_restore(tmp_path, monkeypatch, dry_run, duplicate):
    data = tmp_path / "data"
    data.mkdir()
    config = tmp_path / "config.yaml"
    config.write_bytes(b"current config")
    seat_names = data / "seat_names.json"
    seat_names.write_bytes(b'{"current": true}')
    archive = tmp_path / "duplicate.zip"
    manifest = json.dumps({"included": ["config.yaml", "seat_names.json"]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("manifest.json", manifest)
            zf.writestr("config.yaml", "archived config")
            zf.writestr("seat_names.json", "{}")
            zf.writestr(duplicate, manifest if duplicate == "manifest.json" else "different payload")
    svc = RestoreService(install_dir=tmp_path, data_dir=data, config_path=config,
                         backup_dir=tmp_path / "backups")
    backup = Mock(side_effect=AssertionError("backup must not run"))
    monkeypatch.setattr(svc, "_create_pre_restore_backup", backup)
    monkeypatch.setattr("application.evidence_snapshot_service.EvidenceSnapshotService.capture", lambda *a, **k: None)

    with pytest.raises(RestoreError, match="[Dd]uplicate"):
        svc.restore(archive, dry_run=dry_run)

    backup.assert_not_called()
    assert config.read_bytes() == b"current config"
    assert seat_names.read_bytes() == b'{"current": true}'
