"""Direct camera UI operations count as operator activity, not feedback."""
import os
from pathlib import Path
import subprocess
import sys


def test_direct_controls_refresh_activity_in_clean_qt_process():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from ui.right_panel import RightPanel
app = QApplication([])
window = QWidget()
window.Cam1 = QPushButton(window)
window.Cam1.setCheckable(True)
window.Cam1.setChecked(True)
window._record_activity = Mock()
window._camera_port = Mock()
window._camera_port.focus_auto.return_value = SimpleNamespace(ok=False)
window._camera_port.focus_manual.return_value = SimpleNamespace(ok=False)
window._camera_port.one_push_af.return_value = SimpleNamespace(ok=False)
window._camera_port.brightness_up.return_value = SimpleNamespace(ok=False)
window._camera_port.brightness_down.return_value = SimpleNamespace(ok=False)
window._camera_port.backlight_toggle.return_value = SimpleNamespace(ok=False)
panel = object.__new__(RightPanel)
panel._mw = window
panel._container = QWidget()
layout = QVBoxLayout(panel._container)
panel._add_focus_exposure(layout)
class InlineThread:
    def __init__(self, target, args=(), **kw): self.target, self.args = target, args
    def start(self): self.target(*self.args)
with patch('ui.right_panel.threading.Thread', InlineThread):
    for button in (panel.btn_auto_focus, panel.btn_manual_focus, panel.btn_one_push_af,
                   panel.btn_brighter, panel.btn_darker, window.BtnBacklight):
        window._record_activity.reset_mock()
        button.click()
        window._record_activity.assert_called_once_with()
panel._container.close()
window.close()
'''
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_zoom_feedback_does_not_count_as_operator_activity():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    window = MainWindow()
    window._record_activity = Mock()
    window._zoom_feedback = False
    window.ZoomSlider.setValue(37)
    window._record_activity.assert_called_once_with()
    window._record_activity.reset_mock()
    window._zoom_feedback = True
    window.ZoomSlider.setValue(49)
    window._record_activity.assert_not_called()
    window._zoom_timer.stop()
    window.hide()
    sim.deactivate()
'''
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
