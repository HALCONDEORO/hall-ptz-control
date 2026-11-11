"""CRC errors in unhashed historical backups must fail before restoring files."""
import json
import struct
import zipfile

import pytest

from application.restore_service import RestoreError, RestoreService


def corrupt_backup(path):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', json.dumps({
            'included': ['config.yaml', 'seat_names.json']}))
        archive.writestr('config.yaml', 'site: {name: restored}')
        archive.writestr('seat_names.json', '{"restored": true}')
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('seat_names.json')
        offset = info.header_offset
    data = bytearray(path.read_bytes())
    name_len, extra_len = struct.unpack_from('<HH', data, offset + 26)
    data[offset + 30 + name_len + extra_len] ^= 1
    path.write_bytes(data)


@pytest.mark.parametrize('dry_run', [False, True])
def test_bad_crc_refused_as_restore_error_before_any_write(tmp_path, monkeypatch, dry_run):
    config = tmp_path / 'config.yaml'
    config.write_text('site: {name: current}', encoding='utf-8')
    data = tmp_path / 'data'
    data.mkdir()
    seat_names = data / 'seat_names.json'
    seat_names.write_text('{"current": true}', encoding='utf-8')
    archive = tmp_path / 'corrupt.zip'
    corrupt_backup(archive)
    svc = RestoreService(install_dir=tmp_path, data_dir=data,
                         config_path=config, backup_dir=tmp_path / 'backups')
    calls = []
    def should_not_backup():
        calls.append('backup')
        backup = tmp_path / 'pre-restore.zip'
        backup.write_bytes(b'synthetic safety backup')
        return backup
    monkeypatch.setattr(svc, '_create_pre_restore_backup', should_not_backup)
    original_config = config.read_bytes()
    original_seats = seat_names.read_bytes()

    error = None
    try:
        if dry_run:
            svc._dry_run_inner(archive)
        else:
            svc._restore_inner(archive)
    except Exception as exc:
        error = exc

    assert config.read_bytes() == original_config
    assert seat_names.read_bytes() == original_seats
    assert isinstance(error, RestoreError)
    assert not calls
    assert config.read_bytes() == original_config
    assert seat_names.read_bytes() == original_seats
