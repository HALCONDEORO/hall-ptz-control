"""A hashed member cannot disappear from a backup without failing validation."""
import json
import zipfile

import pytest

from application.backup_service import BackupService
from application.restore_service import RestoreError, RestoreService


@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('missing', ['seat_names.json', 'camera_overrides.json', 'config.yaml'])
def test_missing_hashed_member_is_rejected_before_any_restore(tmp_path, dry_run, missing):
    data = tmp_path / 'data'
    data.mkdir()
    config = tmp_path / 'config.yaml'
    config.write_text('cameras: []')
    for name in ['seat_names.json', 'camera_overrides.json']:
        (data / name).write_text(json.dumps({'state': 'archived'}))
    args = dict(install_dir=tmp_path, data_dir=data, config_path=config,
                backup_dir=tmp_path / 'backups')
    complete = BackupService(**args).create_backup().path
    incomplete = tmp_path / 'incomplete.zip'
    with zipfile.ZipFile(complete) as src, zipfile.ZipFile(incomplete, 'w') as dest:
        for name in src.namelist():
            if name != missing:
                dest.writestr(name, src.read(name))
    config.write_text('cameras: [CURRENT]')
    for name in ['seat_names.json', 'camera_overrides.json']:
        (data / name).write_text(json.dumps({'state': 'current'}))
    before = {p: p.read_bytes() for p in [config, *data.iterdir()]}
    backups_before = set(args['backup_dir'].iterdir())
    with pytest.raises(RestoreError, match='[Mm]issing'):
        RestoreService(**args).restore(incomplete, dry_run=dry_run)
    assert {p: p.read_bytes() for p in before} == before
    assert set(args['backup_dir'].iterdir()) == backups_before
