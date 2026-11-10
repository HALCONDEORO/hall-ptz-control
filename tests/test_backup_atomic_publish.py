"""Failed backup export must not destroy a previous usable archive."""
import zipfile

import pytest

from application.backup_service import BackupService


def service(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'seat_names.json').write_text('{"name": "new"}')
    config = tmp_path / 'config.yaml'
    config.write_text('cameras: []')
    return BackupService(install_dir=tmp_path, data_dir=data, config_path=config,
                         backup_dir=tmp_path / 'backups')


def fail_member_write(monkeypatch):
    original = zipfile.ZipFile.writestr

    def writestr(self, name, *args, **kwargs):
        if name == 'seat_names.json':
            raise OSError('simulated disk/write failure')
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, 'writestr', writestr)


def test_failed_export_preserves_existing_backup(tmp_path, monkeypatch):
    svc = service(tmp_path)
    dest = tmp_path / 'export.zip'
    svc.create_backup(dest)
    previous = dest.read_bytes()
    fail_member_write(monkeypatch)
    with pytest.raises(OSError):
        svc.create_backup(dest)
    assert dest.read_bytes() == previous


def test_failed_export_does_not_publish_incomplete_new_backup(tmp_path, monkeypatch):
    svc = service(tmp_path)
    dest = tmp_path / 'export.zip'
    fail_member_write(monkeypatch)
    with pytest.raises(OSError):
        svc.create_backup(dest)
    assert not dest.exists()


def test_successful_export_replaces_previous_backup(tmp_path):
    svc = service(tmp_path)
    dest = tmp_path / 'export.zip'
    svc.create_backup(dest)
    (svc._data_dir / 'seat_names.json').write_text('{"name": "updated"}')
    result = svc.create_backup(dest)
    assert result.path == dest
    with zipfile.ZipFile(dest) as archive:
        assert archive.read('seat_names.json') == b'{"name": "updated"}'


def test_replace_failure_keeps_previous_archive(tmp_path, monkeypatch):
    svc = service(tmp_path)
    dest = tmp_path / 'export.zip'
    svc.create_backup(dest)
    previous = dest.read_bytes()
    from core import atomic_write

    def fail_replace(*args):
        raise OSError('simulated replace failure')

    monkeypatch.setattr(atomic_write.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        svc.create_backup(dest)
    assert dest.read_bytes() == previous
    assert not list(tmp_path.glob('export.zip.*.tmp'))
