"""A VISCA hex-byte identity does not depend on letter case."""
import pytest
from config.loader import build_settings, ConfigError


@pytest.mark.parametrize('first,second', [('8A', '8a'), ('8a', '8A'), ('8A', '8A')])
def test_duplicate_visca_byte_rejected_regardless_of_case(first, second):
    raw = {'cameras': [
        {'id': 'platform', 'role': 'platform', 'ip': '192.0.2.11', 'visca_id': first},
        {'id': 'comments', 'role': 'comments', 'ip': '192.0.2.12', 'visca_id': second},
    ]}
    with pytest.raises(ConfigError) as failure:
        build_settings(raw)
    assert failure.value.field_path == 'cameras[1].visca_id'
