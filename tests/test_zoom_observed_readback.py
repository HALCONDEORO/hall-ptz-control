"""A settled absolute-zoom intent reads observed feedback, including failures."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('outcome', ['ok', 'failed', 'exception'])
@pytest.mark.parametrize('context', ['same', 'camera_switch', 'ended', 'new_session', 'closing', 'debounce'])
def test_real_zoom_controls_read_observation_after_command_settles(outcome, context):
    script = r'''
import threading, time, sys
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from ui.right_panel import RightPanel
app = QApplication([])
w = QWidget()
w.Cam1 = QPushButton(w); w.Cam1.setCheckable(True); w.Cam1.setChecked(True)
w.Cam2 = QPushButton(w)
w.session_active = True; w._session = Mock(_session_generation=1); w._shutting_down = False
entered, release = threading.Event(), threading.Event()
def command(cam, value):
    entered.set(); release.wait(2)
    if sys.argv[1] == 'exception': raise OSError('synthetic failure')
    return Mock(ok=sys.argv[1] == 'ok')
p = Mock(); p.zoom_absolute = Mock(side_effect=command); w._camera_port = p
w._refresh_zoom = Mock()
panel = object.__new__(RightPanel); panel._mw = w; panel._container = QWidget()
with patch('adapters.sim_mode.is_active', return_value=False):
    panel._add_ptz_block(QVBoxLayout(panel._container))
def observed():
    w._zoom_feedback = True
    try: w.ZoomSlider.setValue(23)
    finally: w._zoom_feedback = False
w._refresh_zoom = Mock(side_effect=observed)
w.ZoomSlider.setValue(77); w._zoom_timer.stop(); w._zoom_timer.timeout.emit()
assert entered.wait(1)
assert w.ZoomValueLabel.text() == '77%'
context = sys.argv[2]
if context == 'camera_switch': w.Cam1.setChecked(False)
if context == 'ended': w.session_active = False
if context == 'new_session': w._session._session_generation = 2
if context == 'closing': w._shutting_down = True
if context == 'debounce': w.ZoomSlider.setValue(88)
release.set()
for _ in range(100):
    app.processEvents(); time.sleep(.005)
    if not panel._zoom_dispatcher._running: break
if context == 'same':
    p.invalidate_zoom.assert_called_once_with(1)
    w._refresh_zoom.assert_called_once()
    assert w.ZoomValueLabel.text() == '23%'
else:
    p.invalidate_zoom.assert_not_called()
    w._refresh_zoom.assert_not_called()
    assert w.ZoomValueLabel.text() == ('88%' if context == 'debounce' else '77%')
w._zoom_timer.stop()
p.zoom_absolute.assert_called_once_with('cam1', 77)
'''
    result = subprocess.run([sys.executable, '-c', script, outcome, context],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


def test_dispatcher_only_observes_after_latest_coalesced_intent():
    from PyQt5.QtWidgets import QApplication
    _qapp = QApplication.instance() or QApplication([])
    import threading
    import time
    from unittest.mock import Mock
    from ui.zoom_dispatch import ZoomDispatcher

    entered = threading.Event()
    release = threading.Event()
    calls = []
    def command(camera_id, value):
        calls.append((camera_id, value))
        if len(calls) == 1:
            entered.set()
            release.wait(2)
    dispatcher = ZoomDispatcher(lambda: 1)
    observed = []
    dispatcher.settled.connect(observed.append)
    port = Mock(zoom_absolute=command)
    dispatcher.submit(port, 'cam1', 10)
    assert entered.wait(1)
    dispatcher.submit(port, 'cam2', 20)
    dispatcher.submit(port, 'cam1', 30)
    release.set()
    for _ in range(200):
        _qapp.processEvents()
        if not dispatcher._running:
            break
        time.sleep(.005)
    assert calls == [('cam1', 10), ('cam1', 30)]
    assert observed == ['cam1']
