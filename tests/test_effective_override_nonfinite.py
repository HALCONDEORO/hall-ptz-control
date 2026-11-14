"""A corrupted numeric override must not break startup or future camera saves."""
import json

import pytest
import yaml

from config.effective import load_effective_config, patch_runtime_config
from config.loader import ConfigError, build_settings, load_config


@pytest.fixture
def config_and_overlay(tmp_path):
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump({'cameras': [
        {'id': 'platform', 'role': 'platform', 'ip': '192.0.2.11', 'visca_id': '81'},
        {'id': 'comments', 'role': 'comments', 'ip': '192.0.2.12', 'visca_id': '82'},
    ]}))
    return config, tmp_path / 'camera_overrides.json'


@pytest.mark.parametrize('check_fallback_first', [True, False])
@pytest.mark.parametrize('field', ['pan_speed', 'duration_ms'])
@pytest.mark.parametrize('number', ['1e999', '-1e999'])
def test_overflowing_override_falls_back_and_allows_next_camera_save(
        config_and_overlay, field, number, check_fallback_first):
    config, overlay = config_and_overlay
    original_yaml = config.read_bytes()
    raw = '{"schema_version":1,"atem":{"pip_nudge":{"' + field + '":' + number + '}}}'
    overlay.write_text(raw)
    if check_fallback_first:
        assert load_effective_config(config, overlay) == load_config(config)
    patch_runtime_config(config, overlay_path=overlay, cam_index=1, cam_ip='192.0.2.22')
    assert config.read_bytes() == original_yaml
    assert load_effective_config(config, overlay).cameras[1].ip == '192.0.2.22'
    preserved = list(overlay.parent.glob('camera_overrides.corrupt.*.json'))
    assert len(preserved) == 1
    assert preserved[0].read_text() == raw
    assert json.loads(overlay.read_text())['cameras']['comments']['ip'] == '192.0.2.22'


@pytest.mark.parametrize('field', ['pan_speed', 'duration_ms'])
@pytest.mark.parametrize('number', [float('inf'), float('-inf')])
def test_nonfinite_nudge_is_a_structured_config_error(config_and_overlay, field, number):
    config, _ = config_and_overlay
    raw = yaml.safe_load(config.read_text())
    raw['atem'] = {'pip_nudge': {field: number}}
    with pytest.raises(ConfigError) as error:
        build_settings(raw)
    assert error.value.field_path == f'atem.pip_nudge.{field}'
