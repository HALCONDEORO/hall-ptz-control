"""Calibration metadata must describe the preset actually being tested."""
import json
from unittest.mock import patch

import pytest

from application.preset_sources import build_items_from_assigned_names, build_items_from_config
from domain.preset_verification import PresetVerification, VerificationStatus


@pytest.mark.parametrize('source', ['config', 'names'])
@pytest.mark.parametrize('field,value', [('preset', 99), ('seat_id', 'seat_099'),
                                        ('camera_id', 'main')])
def test_mismatched_verification_is_not_reused(tmp_path, source, field, value):
    path = tmp_path / 'verifications.json'
    rec = PresetVerification('seat_004', 'comments', 4,
                             status=VerificationStatus.OK).to_dict()
    rec[field] = value
    path.write_text(json.dumps({'seat_004:comments': rec}))
    with patch('config.SEAT_POSITIONS', {4: (0, 0)}), \
         patch('config.PRESET_MAP', {4: '0x04'}), \
         patch('config.load_names_data', return_value={'seats': {'4': 'Name'}}):
        build = build_items_from_config if source == 'config' else build_items_from_assigned_names
        items = build(verifications_path=path)
    assert len(items) == 1
    assert items[0].preset == 4
    assert items[0].has_verified_ptz is None
