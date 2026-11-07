"""Focus feedback must follow confirmed commands, not remain at startup auto."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager


@pytest.mark.parametrize('method,expected', [('focus_manual', 'manual'),
                                             ('focus_auto', 'auto')])
def test_confirmed_focus_updates_manager_feedback(method, expected):
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    manager.focus_mode[1] = 'manual' if expected == 'auto' else 'auto'
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    adapter._send_confirmed = Mock(return_value=True)
    assert getattr(adapter, method)('cam1').ok
    assert manager.focus_mode[1] == expected
    assert manager.focus_mode[2] == 'auto'


@pytest.mark.parametrize('method', ['focus_auto', 'focus_manual'])
@pytest.mark.parametrize('retired', [False, True])
def test_failed_or_retired_focus_preserves_feedback(method, retired):
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    manager.focus_mode[1] = 'prior-mode'
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})

    def confirm(*args):
        if retired:
            adapter.update_camera_visca_id(1, '83')
            return True
        return False

    adapter._send_confirmed = confirm
    getattr(adapter, method)('cam1')
    assert manager.focus_mode[1] == 'prior-mode'


@pytest.mark.parametrize('lifecycle', ['alive', 'deleted', 'shutdown', 'queued_shutdown', 'queued_deleted'])
@pytest.mark.parametrize('ok', [True, False])
@pytest.mark.parametrize('method', ['focus_auto', 'focus_manual', 'one_push_af'])
def test_real_focus_buttons_queue_feedback_without_qt_stub_contamination(ok, method, lifecycle):
    import os
    from pathlib import Path
    import subprocess
    import sys

    script = (
        "import runpy,sys,pytest; ns=runpy.run_path(sys.argv[1]); "
        "ns['_assert_focus_button'](pytest.MonkeyPatch(),sys.argv[2]=='True',sys.argv[3],sys.argv[4])"
    )
    completed = subprocess.run(
        [sys.executable, '-c', script, str(Path(__file__).resolve()), str(ok), method, lifecycle],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
        text=True, capture_output=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _assert_focus_button(monkeypatch, ok, method, lifecycle):
    from PyQt5.QtCore import QObject, pyqtSlot
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
    from ui.right_panel import RightPanel
    from ui.camera_display_mixin import CameraDisplayMixin
    from PyQt5 import sip
    app = QApplication.instance() or QApplication([])

    class Window(QObject, CameraDisplayMixin):
        def __init__(self):
            super().__init__()
            self.Cam1 = Mock()
            self.Cam1.isChecked.return_value = True
            self._camera_port = Mock()
            getattr(self._camera_port, method).return_value = SimpleNamespace(ok=ok)
            self.updates = 0

        @pyqtSlot()
        def _update_focus_ui(self):
            self.updates += 1

    pending = []

    class DeferredThread:
        def __init__(self, target, args=(), **kwargs):
            self.target, self.args = target, args

        def start(self):
            pending.append(lambda: self.target(*self.args))

    monkeypatch.setattr('ui.right_panel.threading.Thread', DeferredThread)
    window = Window()
    panel = RightPanel.__new__(RightPanel)
    panel._mw = window
    panel._container = QWidget()
    panel._add_focus_exposure(QVBoxLayout(panel._container))
    button = {'focus_auto': panel.btn_auto_focus, 'focus_manual': panel.btn_manual_focus,
              'one_push_af': panel.btn_one_push_af}[method]
    button.click()
    assert window.updates == 0
    if lifecycle == 'deleted':
        sip.delete(window)
    elif lifecycle == 'shutdown':
        window._shutting_down = True
    pending.pop()()
    if lifecycle == 'queued_shutdown':
        window._shutting_down = True
    elif lifecycle == 'queued_deleted':
        sip.delete(window)
    app.processEvents()
    getattr(window._camera_port, method).assert_called_once_with('cam1')
    assert window.updates == int(ok and method != 'one_push_af' and lifecycle == 'alive')
