"""Malformed inquiries must not invent a usable exposure setting."""
import pytest
from ptz.visca import parser


@pytest.mark.parametrize("frame", [
    b"", b"\x90\x50\x03", b"\x81\x50\x03\xff",
    b"\x90\x60\x03\xff", b"\x90\x50\x03\x00\xff",
    b"\x90\x50\x7e\xff", b"\x90\x50\xff\xff",
])
def test_invalid_ae_frame_is_unknown(frame):
    assert parser.ae_mode(frame) is None


@pytest.mark.parametrize("frame", [
    b"\x90\x50\x00\x00\x00\x07",  # missing FF
    b"\x81\x50\x00\x00\x00\x07\xff",
    b"\x90\x60\x00\x00\x00\x07\xff",
    b"\x90\x50\x00\x00\x00\x07\x00\xff",
])
def test_invalid_exposure_frame_is_unknown(frame):
    assert parser.exp_comp_level(frame) is None


def test_unknown_ae_does_not_trigger_followup_or_fake_auto(monkeypatch):
    from unittest.mock import Mock
    from adapters.visca_camera_adapter import ViscaCameraAdapter

    worker = Mock()
    worker.send_inquiry.return_value = b"\x90\x50\x7e\xff"
    manager = Mock()
    manager.worker.return_value = worker
    adapter = ViscaCameraAdapter(manager, {1: ("192.0.2.1", "81")})
    assert adapter._query_ae_and_exp_comp("192.0.2.1", "81") == (None, None)
    assert worker.send_inquiry.call_count == 1
