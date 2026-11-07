"""Valid JSON with damaged shapes must not break preset test sources."""
import json

import pytest

from application.preset_verification_service import PresetVerificationService
from domain.preset_verification import PresetVerification, VerificationStatus


@pytest.mark.parametrize('payload', [None, [], [1], 'damaged', 17, True])
def test_non_object_root_is_ignored(tmp_path, payload):
    path = tmp_path / 'verification.json'
    path.write_text(json.dumps(payload))
    assert PresetVerificationService(path).load_all() == {}


@pytest.mark.parametrize('damaged', [None, [], 'bad', 17, True,
                                    {'preset': None}, {'preset': []},
                                    {'preset': {}}])
def test_bad_record_does_not_hide_good_record(tmp_path, damaged):
    path = tmp_path / 'verification.json'
    good = PresetVerification('seat_004', 'comments', 4,
                              status=VerificationStatus.OK).to_dict()
    path.write_text(json.dumps({'bad:comments': damaged,
                                'seat_004:comments': good}))
    records = PresetVerificationService(path).load_all()
    assert list(records) == ['seat_004:comments']
    assert records['seat_004:comments'].is_verified


def test_invalid_utf8_is_ignored(tmp_path):
    path = tmp_path / 'verification.json'
    path.write_bytes(b'\xff\xfe\x80')
    assert PresetVerificationService(path).load_all() == {}
