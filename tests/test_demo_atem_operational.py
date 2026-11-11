"""Demo/sim ATEM surfaces stay reachable with the FakeATEM switcher.

Regression of 38e03f4 ("Hide ATEM controls unless the ATEM is verified
operational"): the operational gate assumed a live ATEMMonitor, so in
demo/simulation mode (FakeATEM, no monitor, possibly no configured IP)
`atem_operational()` was permanently False. The ATEM button stayed hidden,
the demo panel could never open, and the right panel dropped every fake
program update. In demo the FakeATEM itself is the operative surface.
"""
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
from unittest.mock import Mock

from domain.atem_state import ATEMState
from ui.atem_button_state import apply_atem_button_state, _DOT_GREEN, _DOT_RED
from ui.atem_operational import atem_operational


def _fake(connected: bool):
    return SimpleNamespace(
        get_status=lambda: SimpleNamespace(connected=connected))


def _demo_window(connected: bool):
    # Demo/sim window: FakeATEM present, no live monitor, no configured IP.
    return SimpleNamespace(
        _fake_atem=_fake(connected),
        _atem_monitor=None,
        _atem_state=ATEMState.CONNECTED,
        _atem_verified_monitor=None,
        _atem_is_configured=lambda: False,
    )


def test_demo_fake_connected_is_operational_without_monitor_or_ip():
    assert atem_operational(_demo_window(connected=True))


def test_demo_fake_disconnected_is_not_operational():
    assert not atem_operational(_demo_window(connected=False))


def test_demo_fake_status_error_is_not_operational():
    def _boom():
        raise RuntimeError("fake status blew up")
    window = _demo_window(connected=True)
    window._fake_atem = SimpleNamespace(get_status=_boom)
    assert not atem_operational(window)


def test_production_window_without_fake_keeps_strict_gate():
    window = _demo_window(connected=True)
    window._fake_atem = None
    assert not atem_operational(window)  # monitor None → not operational


def test_button_state_demo_connected_shows_green_and_enabled():
    btn, dot, panel = Mock(), Mock(), Mock()
    apply_atem_button_state(
        btn, dot, panel, ATEMState.CONNECTED, _fake(True), operative=True)
    btn.setVisible.assert_called_with(True)
    btn.setEnabled.assert_called_with(True)
    dot.setStyleSheet.assert_called_with(_DOT_GREEN)


def test_button_state_demo_disconnected_keeps_reconnect_reachable():
    # #921: the demo panel owns the Reconnect control, so a disconnected
    # FakeATEM must not hide the button nor force-close the panel.
    btn, dot, panel = Mock(), Mock(), Mock()
    apply_atem_button_state(
        btn, dot, panel, ATEMState.DISCONNECTED, _fake(False), operative=False)
    btn.setVisible.assert_called_with(True)
    btn.setEnabled.assert_called_with(True)
    dot.setStyleSheet.assert_called_with(_DOT_RED)
    panel.hide.assert_not_called()


def test_button_state_production_unverified_stays_hidden():
    btn, dot, panel = Mock(), Mock(), Mock()
    apply_atem_button_state(
        btn, dot, panel, ATEMState.CONNECTED, None, operative=False)
    btn.setVisible.assert_called_with(False)
    panel.hide.assert_called_once()


def test_toggle_opens_demo_panel_even_when_fake_disconnected():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
app = QApplication([])
stub = SimpleNamespace(
    _atem_panel=Mock(),
    _fake_atem=Mock(),
    _btn_atem=Mock(),
    _atem_write_adapter=None,
    _close_atem_panel=Mock(),
)
stub._atem_panel.isVisible.return_value = False
stub.atem_operational = lambda: False  # fake disconnected
MainWindow._toggle_atem_panel(stub)
stub._close_atem_panel.assert_not_called()
stub._atem_panel.setVisible.assert_called_once_with(True)
stub._btn_atem.setChecked.assert_called_once_with(True)
# Production window (no fake) with no operational ATEM still refuses.
prod = SimpleNamespace(
    _atem_panel=Mock(),
    _fake_atem=None,
    _btn_atem=Mock(),
    _atem_write_adapter=Mock(),
    _close_atem_panel=Mock(),
)
prod._atem_panel.isVisible.return_value = False
prod.atem_operational = lambda: False
MainWindow._toggle_atem_panel(prod)
prod._close_atem_panel.assert_called_once()
prod._atem_panel.setVisible.assert_not_called()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
