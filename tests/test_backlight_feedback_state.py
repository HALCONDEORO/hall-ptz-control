"""Confirmed backlight control must update the state consumed by the UI."""
from types import SimpleNamespace
from pathlib import Path
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager


def test_confirmed_backlight_updates_manager_feedback():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81'),
                                           2: ('192.0.2.2', '82')})
    adapter._send_confirmed = Mock(return_value=True)
    assert adapter.backlight_toggle('cam1').ok
    assert manager.backlight_on[1] is True
    assert manager.backlight_on[2] is False


@pytest.mark.parametrize("ok", [True, False])
def test_backlight_button_applies_confirmed_feedback_on_ui_thread(ok):
    # Collection-time Qt stubs can mutate the real QtWidgets module itself.
    # Exercise actual widgets in a fresh process, never skip this regression.
    script = (
        "import runpy, sys, pytest; "
        "namespace = runpy.run_path(sys.argv[1]); "
        "patch = pytest.MonkeyPatch(); "
        "namespace['_assert_backlight_ui_feedback'](patch, sys.argv[2] == 'True')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(Path(__file__).resolve()), str(ok)],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _assert_backlight_ui_feedback(monkeypatch, ok):
    from conftest import ensure_real_qt
    ensure_real_qt()
    from PyQt5.QtCore import QObject, pyqtSlot
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
    from ui.right_panel import RightPanel
    app = QApplication.instance() or QApplication([])

    class Window(QObject):
        def __init__(self):
            super().__init__()
            self.Cam1 = Mock()
            self.Cam1.isChecked.return_value = True
            self._camera_port = Mock()
            self._camera_port.backlight_toggle.return_value = SimpleNamespace(ok=ok)
            self.updates = 0

        @pyqtSlot()
        def _update_backlight_ui(self):
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
    window.BtnBacklight.click()
    assert window.updates == 0
    pending.pop()()
    app.processEvents()
    assert window.updates == int(ok)


def test_failed_or_retired_toggle_preserves_manager_state():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    adapter._send_confirmed = Mock(return_value=False)
    assert not adapter.backlight_toggle('cam1').ok
    assert manager.backlight_on[1] is False

    def retired(*args):
        adapter.update_camera_visca_id(1, '83')
        return True

    adapter._send_confirmed = retired
    adapter.backlight_toggle('cam1')
    assert manager.backlight_on[1] is False
