"""Run Qt-sensitive checks in a fresh interpreter, away from suite stubs."""
import os
from pathlib import Path
import subprocess
import sys

if os.environ.get('KHPTZ_ISOLATED_TEST_STARTUP_POWER_PROMPT_PY') != '1':
    def test_isolated_qt_regressions():
        env = dict(os.environ, KHPTZ_ISOLATED_TEST_STARTUP_POWER_PROMPT_PY='1', QT_QPA_PLATFORM='offscreen')
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(Path(__file__).resolve()),
             '-q', '-o', 'addopts='], env=env, capture_output=True, text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
else:
    """Startup prompt is touch sized, asynchronous, and uses the session path."""
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    import pytest


    @pytest.fixture
    def window(monkeypatch):
        from conftest import ensure_real_qt
        ensure_real_qt()
        from PyQt5.QtWidgets import QApplication, QWidget
        import config
        app = QApplication.instance() or QApplication([])
        monkeypatch.setattr(config.CAM1, 'ip', '192.0.2.11')
        monkeypatch.setattr(config.CAM2, 'ip', '192.0.2.12')
        widget = QWidget()
        widget.session_active = False
        widget._session = SimpleNamespace(ToggleSession=Mock())
        yield widget, app
        widget.close()
        app.processEvents()


    def prompt(window):
        from ui.main_window import MainWindow
        MainWindow._maybe_prompt_power_on(window)


    def test_returns_without_nested_event_loop_and_has_full_touch_buttons(window):
        from PyQt5.QtWidgets import QMessageBox
        widget, app = window
        with patch.object(QMessageBox, 'exec_', side_effect=AssertionError('blocking dialog')):
            prompt(widget)
        app.processEvents()
        box = widget._startup_power_prompt
        assert box.text() == 'Turn on the cameras now?'
        assert [b.text() for b in box.buttons()] == ['Turn on cameras', 'Not now']
        assert all(b.height() >= 52 for b in box.buttons())
        widget._session.ToggleSession.assert_not_called()
        box.reject()


    @pytest.mark.parametrize('accept', [True, False])
    def test_yes_uses_existing_session_path_no_is_noop(window, accept):
        widget, app = window
        prompt(widget)
        box = widget._startup_power_prompt
        box.buttons()[0 if accept else 1].click()
        app.processEvents()
        assert widget._session.ToggleSession.call_count == int(accept)
        assert widget._startup_power_prompt is None


    def test_existing_session_or_existing_prompt_never_repeats(window):
        widget, _ = window
        widget.session_active = True
        prompt(widget)
        assert not hasattr(widget, '_startup_power_prompt')
        widget.session_active = False
        prompt(widget)
        first = widget._startup_power_prompt
        prompt(widget)
        assert widget._startup_power_prompt is first
        widget.session_active = True
        first.buttons()[0].click()
        widget._session.ToggleSession.assert_not_called()


    def test_no_camera_never_prompts(window, monkeypatch):
        import config
        widget, _ = window
        monkeypatch.setattr(config.CAM1, 'ip', '')
        monkeypatch.setattr(config.CAM2, 'ip', '')
        prompt(widget)
        assert not hasattr(widget, '_startup_power_prompt')


    def test_startup_done_reaches_prompt_after_login_splash(window):
        from ui.main_window import MainWindow
        widget, _ = window
        widget._splash_overlay = Mock()
        widget._refresh_zoom = Mock()
        widget._right_panel = Mock()
        widget._maybe_prompt_power_on = Mock()
        with patch('adapters.sim_mode.is_active', return_value=False):
            MainWindow._on_startup_done(widget)
        widget._splash_overlay.hide.assert_called_once()
        widget._maybe_prompt_power_on.assert_called_once()
        widget._session.ToggleSession.assert_not_called()


    def test_simulation_preserves_existing_startup_path_without_duplicate_session(window):
        from ui.main_window import MainWindow
        widget, _ = window
        widget._splash_overlay = Mock()
        widget._refresh_zoom = Mock()
        widget._right_panel = Mock()
        widget._maybe_prompt_power_on = Mock()
        with patch('adapters.sim_mode.is_active', return_value=True):
            MainWindow._on_startup_done(widget)
            widget.session_active = True
            MainWindow._on_startup_done(widget)
        widget._session.ToggleSession.assert_called_once()
        widget._maybe_prompt_power_on.assert_not_called()
