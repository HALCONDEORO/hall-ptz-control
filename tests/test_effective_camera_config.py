"""Runtime override persistence must not grant write access to root-owned config."""
from unittest.mock import patch

import pytest
import yaml

from config.effective import load_effective_config, patch_runtime_config
from config.loader import load_config


@pytest.fixture
def paths(tmp_path):
    config = tmp_path / 'etc' / 'config.yaml'
    config.parent.mkdir()
    config.write_text(yaml.safe_dump({
        'cameras': [
            {'id': 'platform', 'role': 'platform', 'ip': '192.0.2.11', 'visca_id': '81'},
            {'id': 'comments', 'role': 'comments', 'ip': '192.0.2.12', 'visca_id': '82'},
        ], 'atem': {'ip': ''},
    }))
    config.chmod(0o440)
    return config, tmp_path / 'data' / 'camera_overrides.json'


def test_persist_reload_preserves_yaml_and_permissions(paths):
    config, overlay = paths
    original = config.read_bytes()
    patch_runtime_config(config, overlay_path=overlay, cam_index=1, cam_ip='192.0.2.22')
    settings = load_effective_config(config, overlay)
    assert settings.cameras[1].ip == '192.0.2.22'
    assert load_config(config).cameras[1].ip == '192.0.2.12'
    assert config.read_bytes() == original
    assert config.stat().st_mode & 0o777 == 0o440
    assert 'secret' not in overlay.read_text()


def test_updates_merge_without_losing_other_endpoints(paths):
    config, overlay = paths
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    patch_runtime_config(config, overlay_path=overlay, cam_index=1, cam_visca_id='83')
    patch_runtime_config(config, overlay_path=overlay, atem_ip='192.0.2.50',
                         atem_pip_nudge={'pan_speed': 2, 'duration_ms': 100})
    settings = load_effective_config(config, overlay)
    assert settings.cameras[0].ip == '192.0.2.21'
    assert settings.cameras[1].visca_id == '83'
    assert settings.atem.ip == '192.0.2.50'
    assert settings.atem.pip_nudge.pan_speed == 2


@pytest.mark.parametrize('raw', [
    '{', '[]', '{"schema_version":2}',
    '{"schema_version":1,"features":{"simulation":true}}',
    '{"schema_version":1,"cameras":{"unknown":{"ip":"192.0.2.40"}}}',
    '{"schema_version":1,"cameras":{"comments":{"role":"platform"}}}',
    '{"schema_version":1,"cameras":{"comments":{"ip":"192.0.2.11"}}}',
    '{"schema_version":1,"cameras":{"comments":{"visca_id":"81"}}}',
    '{"schema_version":1,"atem":{"enabled":true}}',
    '{"schema_version":1,"atem":{"pip_nudge":{"duration_ms":99999}}}',
])
def test_corrupt_or_forbidden_override_falls_back_without_partial_application(paths, raw):
    config, overlay = paths
    overlay.parent.mkdir()
    overlay.write_text(raw)
    assert load_effective_config(config, overlay) == load_config(config)


def test_invalid_save_does_not_replace_previous_valid_override(paths):
    config, overlay = paths
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    previous = overlay.read_bytes()
    with pytest.raises(ValueError):
        patch_runtime_config(config, overlay_path=overlay, cam_index=1, cam_ip='192.0.2.21')
    assert overlay.read_bytes() == previous


def test_failed_atomic_write_does_not_claim_persistence(paths):
    config, overlay = paths
    with patch('config.effective.write_text_atomic', side_effect=PermissionError('denied')):
        with pytest.raises(PermissionError):
            patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    assert not overlay.exists()


def test_backup_restore_roundtrip_includes_override(paths, tmp_path):
    from application.backup_service import BackupService
    from application.restore_service import RestoreService
    config, overlay = paths
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    common = dict(config_path=config, data_dir=overlay.parent, backup_dir=tmp_path / 'backups')
    backup = BackupService(**common).create_backup()
    assert 'camera_overrides.json' in backup.included
    overlay.write_text('{}')
    config.chmod(0o640)
    result = RestoreService(**common).restore(backup.path)
    assert not result.failed
    assert load_effective_config(config, overlay).cameras[0].ip == '192.0.2.21'


def test_old_backup_restored_yaml_clears_stale_overlay(paths, tmp_path):
    from application.backup_service import BackupService
    from application.restore_service import RestoreService
    config, overlay = paths
    overlay.parent.mkdir()
    common = dict(config_path=config, data_dir=overlay.parent, backup_dir=tmp_path / 'backups')
    backup = BackupService(**common).create_backup()
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    config.chmod(0o640)
    service = RestoreService(**common)
    service.restore(backup.path, dry_run=True)
    assert overlay.exists()
    result = service.restore(backup.path)
    assert not result.failed
    assert not overlay.exists()


def test_production_service_writes_overlay_and_survives_reload(paths, monkeypatch):
    from application.camera_config_service import CameraConfigService
    import types
    config, overlay = paths
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(overlay.parent))
    # Exercise production routing without touching real /etc.
    with patch('config.effective.overlay_file', return_value=overlay):
        overlay.parent.mkdir(parents=True)
        overlay.write_text('{"schema_version":1}')
        fake = types.SimpleNamespace(CAM1=types.SimpleNamespace(ip='192.0.2.11',cam_id='81'),
                                     CAM2=types.SimpleNamespace(ip='192.0.2.12',cam_id='82'),
                                     ATEM=types.SimpleNamespace(ip=''))
        svc = CameraConfigService(config_path_provider=lambda: config, config_module=fake)
        assert svc.set_camera_ip(2, '192.0.2.22').code == 'OK'
        assert load_effective_config(config).cameras[1].ip == '192.0.2.22'


def test_wizard_repair_discards_old_override_after_new_config(paths, monkeypatch):
    from application.provisioning_service import ProvisioningService, ProvisioningAnswers
    from runtime.path_resolver import RuntimePathResolver
    config, overlay = paths
    monkeypatch.setenv('KHPTZ_CONFIG_DIR', str(config.parent))
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(overlay.parent))
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    svc = ProvisioningService()
    answers = ProvisioningAnswers(entry_password='test-op', admin_password='test-admin')
    with patch('application.provisioning_service.secret_manager.encrypt_secret'):
        svc.apply_files(answers, RuntimePathResolver())
    assert not overlay.exists()


def test_doctor_uses_effective_endpoints(paths, tmp_path):
    from application.diagnostics_service import DiagnosticsService
    config, overlay = paths
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    service = DiagnosticsService(config_path=config, data_dir=overlay.parent, log_dir=tmp_path / 'logs')
    assert service._load_settings().cameras[0].ip == '192.0.2.21'


def test_cli_cameras_probes_effective_address(paths, monkeypatch):
    from runtime.cli import main
    config, overlay = paths
    monkeypatch.setenv('KHPTZ_CONFIG_DIR', str(config.parent))
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(overlay.parent))
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    with patch('socket.create_connection') as connect:
        assert main(['cameras']) == 0
    assert connect.call_args_list[0].args[0] == ('192.0.2.21', 5678)


def test_repair_prefills_current_effective_values(paths, monkeypatch):
    from application.provisioning_service import ProvisioningService
    from runtime.path_resolver import RuntimePathResolver
    config, overlay = paths
    monkeypatch.setenv('KHPTZ_CONFIG_DIR', str(config.parent))
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(overlay.parent))
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    answers = ProvisioningService().load_existing_answers(RuntimePathResolver())
    assert answers.cameras[0].ip == '192.0.2.21'


def test_concurrent_threads_preserve_both_updates(paths, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    import config.effective as effective
    config, overlay = paths
    patch_runtime_config(config, overlay_path=overlay)
    original_read = effective._read
    start = threading.Barrier(2)

    def slow_read(path):
        raw = original_read(path)
        time.sleep(0.04)  # force the old unlocked RMW race
        return raw

    monkeypatch.setattr(effective, '_read', slow_read)

    def save(index):
        start.wait(timeout=5)
        patch_runtime_config(config, overlay_path=overlay, cam_index=index,
                             cam_ip=f'192.0.2.{21 + index}')

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(save, (0, 1)))
    saved = load_effective_config(config, overlay)
    assert [cam.ip for cam in saved.cameras] == ['192.0.2.21', '192.0.2.22']


def _process_save(config, overlay, index, start):
    import time
    import config.effective as effective
    original_read = effective._read

    def slow_read(path):
        raw = original_read(path)
        time.sleep(0.08)
        return raw

    effective._read = slow_read
    assert start.wait(5)
    patch_runtime_config(config, overlay_path=overlay, cam_index=index,
                         cam_ip=f'192.0.2.{21 + index}')


def test_concurrent_processes_preserve_both_updates(paths):
    import multiprocessing
    config, overlay = paths
    patch_runtime_config(config, overlay_path=overlay)
    context = multiprocessing.get_context('spawn')
    start = context.Event()
    workers = [context.Process(target=_process_save, args=(config, overlay, i, start))
               for i in (0, 1)]
    try:
        for worker in workers:
            worker.start()
        start.set()
        for worker in workers:
            worker.join(10)
            assert worker.exitcode == 0
        saved = load_effective_config(config, overlay)
        assert [cam.ip for cam in saved.cameras] == ['192.0.2.21', '192.0.2.22']
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)


def test_network_handover_reports_saved_effective_camera_ip(paths, monkeypatch):
    from application.network_handover_report import NetworkHandoverReportService
    config, overlay = paths
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(overlay.parent))
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='192.0.2.21')
    report = NetworkHandoverReportService(config_path=config).generate()
    assert report.errors == []
    assert report.cameras[0].ip == '192.0.2.21'
    assert load_config(config).cameras[0].ip == '192.0.2.11'


def test_repair_preserves_nudge_saved_only_in_runtime_overlay(paths, monkeypatch):
    from application.provisioning_service import ProvisioningService, ProvisioningAnswers
    from runtime.path_resolver import RuntimePathResolver
    config, overlay = paths
    monkeypatch.setenv('KHPTZ_CONFIG_DIR', str(config.parent))
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(overlay.parent))
    patch_runtime_config(config, overlay_path=overlay,
                         atem_pip_nudge={'pan_speed': 2, 'duration_ms': 100,
                                         'direction': 'left'})
    assert load_config(config).atem.pip_nudge.pan_speed == 0
    answers = ProvisioningAnswers(entry_password='test-op', admin_password='test-admin')
    with patch('application.provisioning_service.secret_manager.encrypt_secret'):
        ProvisioningService().apply_files(answers, RuntimePathResolver())
    assert not overlay.exists()
    restored = load_config(config).atem.pip_nudge
    assert (restored.pan_speed, restored.duration_ms, restored.direction) == (2, 100, 'left')
