"""CUT/AUTO must not report success while the PyATEMMax link is down."""
from __future__ import annotations

from unittest.mock import MagicMock

from adapters.atem_write_adapter import ATEMWriteAdapter


def _adapter(link_up: bool):
    a = ATEMWriteAdapter("192.0.2.1")
    atem = MagicMock()
    atem.connected = link_up
    a._atem = atem
    a._connected = True
    return a, atem


def test_cut_reports_disconnected_when_link_down_and_sends_nothing():
    a, atem = _adapter(False)
    r = a.cut()
    assert r.ok is False
    assert r.error_code == "DISCONNECTED"
    atem.execCutME.assert_not_called()
    assert "link lost" in r.message


def test_set_preview_reports_disconnected_when_link_down():
    a, atem = _adapter(False)
    r = a.set_preview_input(2)
    assert (r.ok, r.error_code) == (False, "DISCONNECTED")
    atem.setPreviewInputVideoSource.assert_not_called()


def test_instance_kept_and_recovers_when_link_returns():
    a, atem = _adapter(False)
    assert a.cut().ok is False
    atem.connected = True
    assert a.cut().ok is True
    atem.execCutME.assert_called_once_with(0)


def test_cut_still_works_when_link_up():
    a, atem = _adapter(True)
    assert a.cut().ok is True


def test_status_and_diagnostics_report_link_down_not_connected():
    from application.atem_diagnostics_service import AtemDiagnosticsService

    a, atem = _adapter(False)
    status = a.get_status()
    assert status.connected is False
    assert status.program_input is None and status.preview_input is None
    assert "link lost" in status.last_error
    result = AtemDiagnosticsService(a).read_status()
    assert result.ok is False
    assert result.data["connected"] is False
    assert a._atem is atem  # retain library-managed reconnect


def test_status_recovers_when_library_link_returns():
    a, atem = _adapter(False)
    assert a.get_status().connected is False
    atem.connected = True
    atem.programInput[0].videoSource = 3
    atem.previewInput[0].videoSource = 2
    status = a.get_status()
    assert status.connected is True
    assert (status.program_input, status.preview_input) == (3, 2)
