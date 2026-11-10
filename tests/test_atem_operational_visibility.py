"""No dead ATEM control is shown before a verified live program read."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from domain.atem_state import ATEMState
from ui.atem_button_state import apply_atem_button_state


@pytest.mark.parametrize('state', list(ATEMState))
def test_unverified_or_missing_atem_hides_button_dot_and_panel(state):
    button, dot, panel = Mock(), Mock(), Mock()
    apply_atem_button_state(button, dot, panel, state, None, operative=False)
    button.setVisible.assert_called_with(False)
    dot.setVisible.assert_called_with(False)
    panel.hide.assert_called_once()
    button.setChecked.assert_called_with(False)


def test_operational_atem_shows_only_available_controls():
    button, dot, panel = Mock(), Mock(), Mock()
    apply_atem_button_state(button, dot, panel, ATEMState.CONNECTED, None, operative=True)
    button.setVisible.assert_called_with(True)
    dot.setVisible.assert_called_with(True)
    button.setEnabled.assert_called_with(True)
    panel.show.assert_not_called()


def test_fake_disconnection_does_not_keep_a_dead_button_visible():
    button, dot, panel = Mock(), Mock(), Mock()
    fake = SimpleNamespace(get_status=lambda: SimpleNamespace(connected=False))
    apply_atem_button_state(button, dot, panel, ATEMState.CONNECTED, fake, operative=False)
    button.setVisible.assert_called_with(False)
    panel.hide.assert_called_once()


def test_settings_binding_tracks_verification_loss_and_recovery_in_real_qt():
    import os
    from pathlib import Path
    import subprocess
    import sys
    script = r'''
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget
from ui.atem_visibility import bind_operational_visibility
app = QApplication([])
class Window(QWidget):
    atem_state_changed = pyqtSignal(object)
    ready = False
    def atem_operational(self):
        return self.ready
window = Window()
widget = QWidget(window)
bind_operational_visibility(window, widget)
assert widget.isHidden()
window.ready = True
window.atem_state_changed.emit(None)
assert not widget.isHidden()
window.ready = False
window.atem_state_changed.emit(None)
assert widget.isHidden()
widget.deleteLater()
app.processEvents()
window.atem_state_changed.emit(None)
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_late_program_and_pip_cannot_resurrect_status_when_gate_closed():
    import ast
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'ui/right_panel.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RightPanel')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
               and n.name in ('set_atem_program', 'set_pip_state')]
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), str(path), 'exec'), ns)
    panel = SimpleNamespace(_mw=SimpleNamespace(atem_operational=lambda: False),
                            _pip_label=Mock(), _on_air_label=Mock())
    ns['set_atem_program'](panel, 2)
    ns['set_pip_state'](panel, SimpleNamespace(enabled=True, source=2))
    panel._on_air_label.setVisible.assert_not_called()
    panel._pip_label.show.assert_not_called()
    panel._pip_label.hide.assert_called_once()


def test_settings_keeps_ip_but_hides_operations_until_verified():
    import os
    from pathlib import Path
    import subprocess
    import sys
    script = r'''
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from tests.config_pages_harness import make_harness, panel_layout
from ui.config_pages.atem_tab import build_atem_tab
app = QApplication([])
dialog, mw, layout = make_harness()
mw.atem_ready = False
build_atem_tab(dialog, layout, mw, False, False, panel_layout)
dialog.show()
app.processEvents()
automation = next(w for w in dialog.findChildren(QLabel) if w.text() == 'Dispatcher no disponible.')
assert not automation.isVisible()
assert any(w.text() == 'IP' and w.isVisible() for w in dialog.findChildren(QLabel))
mw.atem_ready = True
mw.atem_state_changed.emit(None)
app.processEvents()
assert automation.isVisible()
mw.atem_ready = False
mw.atem_state_changed.emit(None)
app.processEvents()
assert not automation.isVisible()
# Destroy widgets while their signal owner and QApplication still exist.
# Leaving this graph to interpreter shutdown can destroy Qt in the wrong order.
from PyQt5 import sip
from PyQt5.QtCore import QCoreApplication, QEvent, QTimer
for timer in dialog.findChildren(QTimer):
    timer.stop()
dialog.hide()
sip.delete(dialog)
QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
app.processEvents()
sip.delete(mw)
app.processEvents()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
