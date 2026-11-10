"""Malformed section types produce actionable ConfigError, never AttributeError."""
import pytest
from config.loader import build_settings, ConfigError


@pytest.mark.parametrize('section', ['site', 'atem', 'runtime', 'features', 'network'])
@pytest.mark.parametrize('value', ['bad', [1], 7, True, [], '', 0, False])
def test_non_mapping_sections_are_rejected_with_field_path(section, value):
    raw = {'cameras': [{'id': 'platform', 'role': 'platform', 'ip': '192.0.2.11', 'visca_id': '81'}], section: value}
    with pytest.raises(ConfigError) as failure:
        build_settings(raw)
    assert failure.value.field_path == section
