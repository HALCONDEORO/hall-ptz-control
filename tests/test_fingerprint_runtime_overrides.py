"""Known-good comparisons must detect endpoint overrides used by the runtime."""
import json
from pathlib import Path
import shutil

from application.fingerprint_service import FingerprintService
from application.known_good_state_service import KnownGoodStateService
from config.effective import load_effective_config, patch_runtime_config
from runtime.path_resolver import RuntimePathResolver


def _installation(tmp_path, monkeypatch):
    monkeypatch.setenv('KHPTZ_CONFIG_DIR', str(tmp_path / 'config'))
    monkeypatch.setenv('KHPTZ_DATA_DIR', str(tmp_path / 'data'))
    paths = RuntimePathResolver()
    paths.config_dir.mkdir()
    paths.data_dir.mkdir()
    config = paths.config_dir / 'config.yaml'
    shutil.copy(Path(__file__).resolve().parents[1] / 'config/defaults/starter.yaml', config)
    return paths, config


def test_known_good_diff_detects_effective_endpoint_change(tmp_path, monkeypatch):
    paths, config = _installation(tmp_path, monkeypatch)
    service = KnownGoodStateService(paths)
    assert service.mark(force=True).success
    overlay = paths.data_dir / 'camera_overrides.json'

    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='172.16.1.99')

    assert load_effective_config(config).cameras[0].ip == '172.16.1.99'
    diff = service.diff()
    assert not diff.is_clean
    assert 'config_hash' in [change.field for change in diff.changes]


def test_override_hash_is_stable_and_endpoint_sensitive(tmp_path, monkeypatch):
    paths, config = _installation(tmp_path, monkeypatch)
    service = FingerprintService(paths)
    overlay = paths.data_dir / 'camera_overrides.json'
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='172.16.1.99')
    first = service._hash_config()
    content = json.loads(overlay.read_text())
    overlay.write_text(json.dumps(content, sort_keys=True, separators=(',', ':')))
    assert service._hash_config() == first
    patch_runtime_config(config, overlay_path=overlay, cam_index=0, cam_ip='172.16.1.98')
    assert service._hash_config() != first


def test_without_overrides_keeps_existing_base_hash(tmp_path, monkeypatch):
    import hashlib
    from domain.redaction import RedactionGuard
    paths, config = _installation(tmp_path, monkeypatch)
    expected = hashlib.sha256(RedactionGuard().redact_text(config.read_text()).encode()).hexdigest()
    assert FingerprintService(paths)._hash_config() == expected
