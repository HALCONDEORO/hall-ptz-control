"""A restored JSON must not recover pre-restore data from a stale .bak."""
import pytest
from application.backup_service import BackupService
from application.restore_service import RestoreService
from core.json_io import load_json, save_json


def site(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    config = tmp_path / 'config.yaml'
    config.write_text('cameras: []', encoding='utf-8')
    return dict(install_dir=tmp_path, data_dir=data, config_path=config,
                backup_dir=tmp_path / 'backups')


@pytest.mark.parametrize('name', ['seat_names.json', 'chairman_presets.json', 'room_layout.json'])
def test_restore_refreshes_existing_json_recovery_copy(tmp_path, name):
    args = site(tmp_path)
    primary = args['data_dir'] / name
    restored = {'marker': 'restored'}
    assert save_json(primary, restored)
    archive = BackupService(**args).create_backup().path
    assert save_json(primary, {'marker': 'old'})
    assert save_json(primary, {'marker': 'current'})
    assert load_json(primary.with_suffix('.bak')) == {'marker': 'old'}
    result = RestoreService(**args)._restore_inner(archive)
    assert not result.failed
    assert load_json(primary) == restored
    primary.write_text('{', encoding='utf-8')
    assert load_json(primary) == restored


def test_restore_does_not_create_an_unrequested_recovery_copy(tmp_path):
    args = site(tmp_path)
    primary = args['data_dir'] / 'seat_names.json'
    assert save_json(primary, {'marker': 'restored'})
    archive = BackupService(**args).create_backup().path
    RestoreService(**args)._restore_inner(archive)
    assert not primary.with_suffix('.bak').exists()


def test_recovery_copy_write_failure_reports_partial_restore(tmp_path, monkeypatch):
    args = site(tmp_path)
    primary = args['data_dir'] / 'seat_names.json'
    assert save_json(primary, {'marker': 'restored'})
    archive = BackupService(**args).create_backup().path
    assert save_json(primary, {'marker': 'current'})
    svc = RestoreService(**args)
    write = svc._atomic_write
    def fail_bak(data, dest):
        if dest == primary.with_suffix('.bak'):
            raise PermissionError('recovery copy denied')
        return write(data, dest)
    monkeypatch.setattr(svc, '_atomic_write', fail_bak)
    result = svc._restore_inner(archive)
    assert any('seat_names.json' in f for f in result.failed)
