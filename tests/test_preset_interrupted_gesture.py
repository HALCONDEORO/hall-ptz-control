"""Real Qt regressions for interrupted preset input, without camera hardware."""
import pytest

pytest.importorskip("PyQt5")

from conftest import ensure_real_qt


@pytest.fixture
def preset_button():
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


def press(button):
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    QTest.mousePress(button, Qt.LeftButton, pos=QPoint(5, 5))


def release(button):
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    QTest.mouseRelease(button, Qt.LeftButton, pos=QPoint(5, 5))


@pytest.mark.parametrize("event_name", ["Hide", "UngrabMouse", "WindowDeactivate"])
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


def test_actual_hide_cancels_pending_set(preset_button):
    from PyQt5.QtTest import QTest
    app, button, calls, sets = preset_button
    press(button)
    button.hide()
    QTest.qWait(40)
    button.show()
    release(button)
    assert calls == sets == []


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


def test_normal_long_press_sets_once_without_call(preset_button):
    from PyQt5.QtTest import QTest
    app, button, calls, sets = preset_button
    press(button)
    QTest.qWait(40)
    release(button)
    assert sets == [2]
    assert calls == []


def test_stray_release_without_press_cannot_call(preset_button):
    app, button, calls, sets = preset_button
    release(button)
    assert calls == sets == []
