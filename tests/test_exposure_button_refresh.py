"""A confirmed exposure step must read camera feedback, not count clicks."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('method,ok', [('brightness_up', True), ('brightness_down', True),
                                      ('brightness_up', False)])
def test_exposure_click_reads_back_only_after_confirmation(monkeypatch, method, ok):
    from conftest import ensure_real_qt
    ensure_real_qt()
    from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
    from ui.right_panel import RightPanel
    import ui.right_panel as module
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.Cam1 = QPushButton(window)
    window.Cam1.setCheckable(True)
    window.Cam1.setChecked(True)
    port = Mock()
    port.display_generation.return_value = 7
    getattr(port, method).return_value = SimpleNamespace(ok=ok)
    window._camera_port = port
    panel = object.__new__(RightPanel)
    panel._mw = window
    panel._container = QWidget()
    layout = QVBoxLayout(panel._container)
    panel._add_focus_exposure(layout)
    class InlineThread:
        def __init__(self, target, args=(), **kwargs):
            self.target, self.args = target, args
        def start(self):
            self.target(*self.args)
    monkeypatch.setattr(module.threading, 'Thread', InlineThread)
    delivery = Mock()
    monkeypatch.setattr('ui.camera_display_mixin._queue_display_update', delivery)
    (panel.btn_brighter if method == 'brightness_up' else panel.btn_darker).click()
    getattr(port, method).assert_called_once_with('cam1')
    if ok:
        port.async_refresh_ae_mode.assert_called_once()
        key, callback = port.async_refresh_ae_mode.call_args.args
        assert key == 1
        callback()
        assert delivery.call_args.args[1:] == ('_apply_exposure_update', 1, 7)
    else:
        port.async_refresh_ae_mode.assert_not_called()
    window.close()
    panel._container.close()
    app.processEvents()
