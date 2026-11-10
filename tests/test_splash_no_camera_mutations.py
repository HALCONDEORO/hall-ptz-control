"""Startup diagnostics must not touch power/motion/image before consent."""
from unittest.mock import Mock, patch

from ui.splash_screen import SplashScreen


def test_startup_does_not_dispatch_camera_power_phase():
    window = Mock()
    SplashScreen._startup_sequence(window)
    window._startup_cameras.assert_not_called()
    window._run_config_phase.assert_called_once()
    window._run_initialization.assert_called_once()


def test_diagnostic_list_has_no_focus_exposure_write_tests():
    window = Mock()
    window.boot_stats.get_summary.return_value = None
    window.tests_passed = 0
    seen = []
    class Executor:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def submit(self, fn, name, operation):
            seen.append(name)
            return Mock()
    with patch('ui.splash_screen.ThreadPoolExecutor', Executor), \
         patch('ui.splash_screen.as_completed', return_value=[]), \
         patch('ui.splash_screen.time.sleep'):
        SplashScreen._run_initialization(window)
    assert not any('Focus & Exposure' in name for name in seen)
