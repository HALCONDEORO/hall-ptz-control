"""Re-verifying a reassigned preset must update its stored target."""
import json

from application.preset_verification_service import PresetVerificationService
from domain.preset_verification import VerificationStatus


def test_remark_records_new_preset_number(tmp_path):
    path = tmp_path / 'verifications.json'
    service = PresetVerificationService(path)
    service.mark('seat_004', 'comments', 99, VerificationStatus.FAILED)
    result = service.mark('seat_004', 'comments', 4, VerificationStatus.OK)
    assert result.preset == 4
    assert service.get('seat_004', 'comments').preset == 4
    assert service.get('seat_004', 'comments').is_verified


def test_remark_repairs_identity_inside_existing_key(tmp_path):
    path = tmp_path / 'verifications.json'
    path.write_text(json.dumps({'seat_004:comments': {
        'seat_id': 'seat_099', 'camera_id': 'main',
        'preset': 99, 'status': 'failed',
    }}))
    result = PresetVerificationService(path).mark(
        'seat_004', 'comments', 4, VerificationStatus.OK,
    )
    assert (result.seat_id, result.camera_id, result.preset) == ('seat_004', 'comments', 4)
    saved = PresetVerificationService(path).get('seat_004', 'comments')
    assert (saved.seat_id, saved.camera_id, saved.preset) == ('seat_004', 'comments', 4)
