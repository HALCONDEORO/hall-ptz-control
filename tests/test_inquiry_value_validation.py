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

    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("adapters.visca_camera_adapter.socket.socket", Mock(return_value=connection))
    adapter = ViscaCameraAdapter(Mock(), {1: ("192.0.2.1", "81")})
    monkeypatch.setattr(adapter, "_recv_visca_response", Mock(return_value=b"\x90\x50\x7e\xff"))
    assert adapter._query_ae_and_exp_comp("192.0.2.1", "81") == (None, None)
    assert connection.sendall.call_count == 1
