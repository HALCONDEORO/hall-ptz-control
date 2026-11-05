"""Snapshot, restore outcome and session epoch regressions without hardware."""
import hashlib
import json
import threading
import zipfile
from unittest.mock import Mock, patch

from application.backup_service import BackupService
from application.restore_service import RestoreResult, RestoreService
from application.session_service import SessionService


def test_backup_manifest_matches_bytes_even_if_source_changes(tmp_path):
    source = tmp_path / "seat_names.json"
    source.write_bytes(b"FIRST")
    svc = BackupService(install_dir=tmp_path, data_dir=tmp_path,
                        config_path=tmp_path / "config.yaml", backup_dir=tmp_path)
    svc._collect_candidates = lambda: [("seat_names.json", source)]
    real_open = zipfile.ZipFile

    def open_after_change(*args, **kwargs):
        source.write_bytes(b"SECOND")
        return real_open(*args, **kwargs)

    with patch("application.backup_service.zipfile.ZipFile", open_after_change):
        result = svc.create_backup(tmp_path / "backup.zip")
    with real_open(result.path) as archive:
        record = json.loads(archive.read("manifest.json"))["files"][0]
        actual = archive.read("seat_names.json")
    assert record["sha256"] == hashlib.sha256(actual).hexdigest()
    assert record["size_bytes"] == len(actual)


def test_partial_restore_is_not_recorded_as_success(tmp_path):
    svc = RestoreService(install_dir=tmp_path, data_dir=tmp_path,
                         config_path=tmp_path / "config.yaml", backup_dir=tmp_path)
    svc._restore_inner = Mock(return_value=RestoreResult(None, ["one"], [], ["two failed"]))
    svc._record_event = Mock()
    with patch("application.evidence_snapshot_service.EvidenceSnapshotService"):
        result = svc.restore(tmp_path / "source.zip")
    assert result.failed
    events = [c.args[0] for c in svc._record_event.call_args_list]
    assert "RestoreSucceeded" not in events
    assert "RestoreFailed" in events


def test_old_power_sequence_cannot_resume_after_new_session_starts():
    port = Mock()
    port.power_on.return_value = None
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def power_on(cam):
        calls.append((threading.current_thread().name, cam))
        if cam == "cam1" and not entered.is_set():
            entered.set()
            assert release.wait(3)

    port.power_on.side_effect = power_on
    svc = SessionService(port)
    with patch("application.session_service.mark_session_active"), patch(
        "application.session_service.clear_session_marker"
    ):
        svc.start()
        old_thread = svc._power_thread
        assert entered.wait(3)
        svc.end()
        svc._standby_thread.join(3)
        svc.start()
        new_thread = svc._power_thread
        new_thread.join(3)
        release.set()
        old_thread.join(3)
    # Only the new session's sequence may proceed to its second camera.
    assert sum(cam == "cam2" for _, cam in calls) == 1
