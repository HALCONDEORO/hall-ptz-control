"""Appliance state files must survive an interrupted write.

The known-good snapshot and the maintenance record are the recovery and
warranty anchors of an appliance that can lose power at any moment. A crash
mid-write must never leave a torn file that silently destroys the previous
state: writes go through core.atomic_write (private tmp file + fsync +
os.replace), so a failed write leaves the previous file untouched and the
caller sees a clean failure.
"""
import json
import os

import pytest
from unittest.mock import MagicMock, patch

from application.known_good_state_service import (
    KnownGoodSnapshot,
    KnownGoodStateService,
)
from application.maintenance_service import MaintenanceService


def _make_paths(tmp_path):
    mock = MagicMock()
    mock.data_dir = tmp_path / "data"
    mock.known_good_state_file = tmp_path / "data" / "known_good_state.json"
    return mock


def _fail_replace(src, dst):
    raise OSError("simulated power loss during replace")


class TestKnownGoodStateWriteAtomicity:

    def test_failed_write_preserves_previous_snapshot(self, tmp_path, monkeypatch):
        paths = _make_paths(tmp_path)
        paths.known_good_state_file.parent.mkdir(parents=True, exist_ok=True)
        previous = KnownGoodSnapshot(installation_id="khptz-2026-0042", app_version="3.18.0")
        paths.known_good_state_file.write_text(
            json.dumps(previous.to_dict()), encoding="utf-8"
        )

        svc = KnownGoodStateService(paths=paths)
        monkeypatch.setattr(os, "replace", _fail_replace)
        fp = MagicMock(
            installation_id="khptz-2026-0042",
            app_version="3.19.0",
            git_commit="abc123",
            profile="default",
            config_hash="cfg",
            layout_hash="lay",
            cameras=[],
            atem_enabled=False,
            atem_configured=False,
        )
        fp.fingerprint_hash.return_value = "fph"
        with patch.object(KnownGoodStateService, "_find_blockers", return_value=[]), \
             patch("application.fingerprint_service.FingerprintService") as mock_svc:
            mock_svc.return_value.generate.return_value = fp
            result = svc.mark()

        assert not result.success, "mark() must report failure when the write fails"
        loaded = svc.load()
        assert loaded is not None, "interrupted write destroyed the previous known-good snapshot"
        assert loaded.installation_id == "khptz-2026-0042"
        assert loaded.app_version == "3.18.0"


class TestMaintenanceRecordWriteAtomicity:

    def test_failed_write_preserves_previous_record(self, tmp_path, monkeypatch):
        state_file = tmp_path / "maintenance.json"
        previous = {
            "completed_at": "2026-11-01T10:00:00+00:00",
            "completed_by": "operator",
            "notes": "previous run",
            "result": "passed",
        }
        state_file.write_text(json.dumps(previous), encoding="utf-8")

        svc = MaintenanceService(data_dir=tmp_path)
        monkeypatch.setattr(os, "replace", _fail_replace)
        with pytest.raises(OSError, match="simulated power loss"):
            svc.mark_complete(completed_by="operator", notes="new run")

        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["completed_at"] == "2026-11-01T10:00:00+00:00", (
            "interrupted write destroyed the previous maintenance record"
        )
