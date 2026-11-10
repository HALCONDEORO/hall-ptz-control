"""Malformed manifest structures must fail through the restore error contract."""
import json
import zipfile
from unittest.mock import Mock

import pytest

from application.restore_service import RestoreError, RestoreService


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("manifest", [
    None, [], "not-an-object", 1,
    {"included": "config.yaml"},
    {"included": {"config.yaml": True}},
    {"included": None},
    {"included": [None]},
    {"included": [["config.yaml"]]},
])
def test_malformed_manifest_rejected_before_backup_or_data_write(tmp_path, monkeypatch, manifest, dry_run):
    data = tmp_path / "data"
    data.mkdir()
    config = tmp_path / "config.yaml"
    config.write_bytes(b"current configuration")
    current = data / "camera_overrides.json"
    current.write_bytes(b'{"current": true}')
    archive = tmp_path / "malformed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("config.yaml", "archived configuration")
    svc = RestoreService(install_dir=tmp_path, data_dir=data, config_path=config,
                         backup_dir=tmp_path / "backups")
    backup = Mock(side_effect=AssertionError("backup must not run"))
    monkeypatch.setattr(svc, "_create_pre_restore_backup", backup)
    monkeypatch.setattr("application.evidence_snapshot_service.EvidenceSnapshotService.capture", lambda *a, **k: None)

    with pytest.raises(RestoreError, match="[Mm]anifest"):
        svc.restore(archive, dry_run=dry_run)

    backup.assert_not_called()
    assert config.read_bytes() == b"current configuration"
    assert current.read_bytes() == b'{"current": true}'
    assert not (tmp_path / "backups").exists()
