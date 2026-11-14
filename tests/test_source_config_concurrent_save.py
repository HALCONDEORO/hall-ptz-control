"""Source YAML saves must retain both independently edited camera addresses."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

import yaml

from config.effective import patch_runtime_config


def test_two_source_camera_saves_do_not_overwrite_each_other(tmp_path, monkeypatch):
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump({'cameras': [
        {'id': 'platform', 'role': 'platform', 'ip': '192.0.2.11', 'visca_id': '81'},
        {'id': 'comments', 'role': 'comments', 'ip': '192.0.2.12', 'visca_id': '82'},
    ]}))
    overlay = tmp_path / 'absent-runtime' / 'camera_overrides.json'
    monkeypatch.setattr('config.effective.overlay_file', lambda: overlay)
    monkeypatch.setattr('config.effective.RuntimePathResolver.running_from_source', True)
    original_read = Path.read_text
    first_read = threading.Event()
    reads = []

    def slow_read(path, *args, **kwargs):
        text = original_read(path, *args, **kwargs)
        if path == config:
            reads.append(threading.get_ident())
            if len(reads) == 1:
                first_read.set()
                time.sleep(.15)
        return text

    monkeypatch.setattr(Path, 'read_text', slow_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(patch_runtime_config, config, cam_index=0, cam_ip='192.0.2.21')
        assert first_read.wait(2)
        second = pool.submit(patch_runtime_config, config, cam_index=1, cam_ip='192.0.2.22')
        first.result(timeout=3)
        second.result(timeout=3)
    saved = yaml.safe_load(original_read(config))
    assert saved['cameras'][0]['ip'] == '192.0.2.21'
    assert saved['cameras'][1]['ip'] == '192.0.2.22'
    assert not overlay.exists(), 'source save must keep its YAML contract'
