"""Real Qt regressions for interrupted preset input, without camera hardware."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip("PyQt5")

# The whole suite imports Qt stubs and real widgets during collection. Forking
# preserves that process state; exec a clean interpreter so these regressions
# always exercise real Qt without skipping poisoned classes or changing CI.


@pytest.fixture(autouse=True)
def _fresh_qt_process(request):
    if os.environ.get("KHPTZ_PRESET_QT_CHILD") == "1":
        return
    env = dict(os.environ, KHPTZ_PRESET_QT_CHILD="1", QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", request.node.nodeid],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # The child ran this exact test and all its assertions. Do not construct
    # another widget in the contaminated parent.
    request.node._preset_child_passed = True


from conftest import ensure_real_qt


@pytest.fixture
def preset_button(request):
    if getattr(request.node, "_preset_child_passed", False):
        yield None
        return
    ensure_real_qt()
    from PyQt5.QtWidgets import QApplication
    from ui.widgets import PlatformPresetButton
    app = QApplication.instance() or QApplication([])
    calls, sets = [], []
    button = PlatformPresetButton()
    button.init_preset_actions(2, calls.append, sets.append)
    button._long_press_timer.setInterval(20)
    button.show()
    app.processEvents()
    yield app, button, calls, sets
    button.close()


def isolated_qt_test(test):
    """Parent verifies the child result; only the fresh child drives Qt."""
    from functools import wraps

    @wraps(test)
    def wrapped(preset_button, *args, **kwargs):
        if preset_button is not None:
            return test(preset_button, *args, **kwargs)
    return wrapped


def press(button):
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    QTest.mousePress(button, Qt.LeftButton, pos=QPoint(5, 5))


def release(button):
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    QTest.mouseRelease(button, Qt.LeftButton, pos=QPoint(5, 5))


@pytest.mark.parametrize("event_name", ["Hide", "UngrabMouse", "WindowDeactivate"])
@isolated_qt_test
def test_interruption_cancels_set_and_late_release(preset_button, event_name):
    from PyQt5.QtCore import QEvent
    from PyQt5.QtTest import QTest
    app, button, calls, sets = preset_button
    press(button)
    app.sendEvent(button, QEvent(getattr(QEvent, event_name)))
    QTest.qWait(40)
    button._on_long_press()  # A queued timeout after cancellation is also harmless.
    release(button)
    assert not button._long_press_timer.isActive()
    assert not button.isDown()
    assert calls == sets == []


@isolated_qt_test
def test_actual_hide_cancels_pending_set(preset_button):
    from PyQt5.QtTest import QTest
    app, button, calls, sets = preset_button
    press(button)
    button.hide()
    QTest.qWait(40)
    button.show()
    release(button)
    assert calls == sets == []


@isolated_qt_test
def test_disable_cancels_and_new_tap_still_works(preset_button):
    from PyQt5.QtTest import QTest
    app, button, calls, sets = preset_button
    press(button)
    button.setEnabled(False)
    QTest.qWait(40)
    button.setEnabled(True)
    release(button)
    assert calls == sets == []
    press(button)
    release(button)
    assert calls == [2]
    assert sets == []


@isolated_qt_test
def test_normal_long_press_sets_once_without_call(preset_button):
    from PyQt5.QtTest import QTest
    app, button, calls, sets = preset_button
    press(button)
    QTest.qWait(40)
    release(button)
    assert sets == [2]
    assert calls == []


@isolated_qt_test
def test_stray_release_without_press_cannot_call(preset_button):
    app, button, calls, sets = preset_button
    release(button)
    assert calls == sets == []
