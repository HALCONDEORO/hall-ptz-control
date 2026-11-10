"""Real Qt timer must stay responsive while a confirmed zoom waits on hardware."""
import os
from pathlib import Path
import subprocess
import sys


def test_zoom_confirmation_never_blocks_qt_thread():
    script = r'''
import threading
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui.right_panel import RightPanel
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout
from unittest.mock import patch
app = QApplication([])
entered, release = threading.Event(), threading.Event()
calls = []
def zoom(cam, value):
    calls.append((cam, value, threading.current_thread()))
    entered.set()
    release.wait(2)
port = Mock(zoom_absolute=zoom)
active = [True]
window = QWidget()
window.Cam1 = QPushButton(window)
window.Cam1.setCheckable(True)
window.Cam1.setChecked(True)
window.Cam2 = QPushButton(window)
window._camera_port = port
window._refresh_zoom = Mock()
window.session_active = True
window._session = Mock(_session_generation=1)
window._shutting_down = False
panel = object.__new__(RightPanel)
panel._mw = window
panel._container = QWidget()
with patch('adapters.sim_mode.is_active', return_value=False):
    panel._add_ptz_block(QVBoxLayout(panel._container))
window.ZoomSlider.setValue(10)
window._zoom_timer.stop()
window._zoom_timer.timeout.emit()
assert entered.wait(1)
for value in (20, 30):
    window.ZoomSlider.setValue(value)
    window._zoom_timer.stop()
    window._zoom_timer.timeout.emit()
assert len(calls) == 1
seen = []
QTimer.singleShot(0, lambda: seen.append(True))
app.processEvents()
assert seen == [True]
assert calls[0][2] is not threading.current_thread()
# Session ends before the queued latest value may be dispatched.
window.session_active = False
release.set()
import time
for _ in range(20):
    app.processEvents()
    time.sleep(.01)
assert len(calls) == 1
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


def test_zoom_dispatch_coalesces_and_drops_previous_session():
    script = r'''
import threading
import time
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
from ui.zoom_dispatch import ZoomDispatcher
app = QApplication([])
current = [1]
entered, release = threading.Event(), threading.Event()
calls = []
def zoom(cam, value):
    calls.append((cam, value))
    if len(calls) == 1:
        entered.set()
        release.wait(2)
port = Mock(zoom_absolute=zoom)
dispatch = ZoomDispatcher(lambda: current[0])
dispatch.submit(port, 'cam1', 10)
assert entered.wait(1)
dispatch.submit(port, 'cam2', 20)
dispatch.submit(port, 'cam1', 30)
release.set()
for _ in range(100):
    app.processEvents()
    if len(calls) == 2 and not dispatch._running:
        break
    time.sleep(.005)
assert calls == [('cam1', 10), ('cam1', 30)]
# A new session with the same active flag must not inherit pending motion.
entered.clear()
release.clear()
calls.clear()
dispatch.submit(port, 'cam1', 40)
assert entered.wait(1)
dispatch.submit(port, 'cam2', 50)
current[0] = 2
release.set()
for _ in range(30):
    app.processEvents()
    time.sleep(.005)
assert calls == [('cam1', 40)]
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


def test_camera_switch_cancels_unsent_zoom_debounce():
    script = r'''
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from ui.right_panel import RightPanel
app = QApplication([])
window = QWidget()
window.Cam1 = QPushButton(window)
window.Cam2 = QPushButton(window)
window._camera_port = Mock()
window._refresh_zoom = Mock()
window.session_active = True
window._session = Mock(_session_generation=1)
window._shutting_down = False
panel = object.__new__(RightPanel)
panel._mw = window
panel._container = QWidget()
with patch('adapters.sim_mode.is_active', return_value=False):
    panel._add_ptz_block(QVBoxLayout(panel._container))
window.ZoomSlider.setValue(37)
assert window._zoom_timer.isActive()
window.Cam2.click()
assert not window._zoom_timer.isActive(), 'Previous camera zoom intent leaked to new camera'
window._camera_port.zoom_absolute.assert_not_called()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
