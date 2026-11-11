"""Exercise the production preset timer in a clean real Qt interpreter."""
import os
from pathlib import Path
import subprocess
import sys


def test_one_second_threshold_tap_hold_and_drag_cancel():
    script = r'''
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from ui.widgets import GoButton, SpecialDragButton, PlatformPresetButton
from application.call_set_command_policy import CallSetCommandPolicy
from domain.call_set_policy import InputType, OperatingMode, CallSetAction
app = QApplication([])
for make in (lambda: GoButton(42), lambda: SpecialDragButton(42, 'Seat'), PlatformPresetButton):
    widget = make()
    calls, sets = [], []
    widget.init_preset_actions(42, calls.append, sets.append)
    assert widget.LONG_PRESS_MS == 1000
    assert widget._long_press_timer.interval() == 1000
    widget.show()
    app.processEvents()
    # A sub-threshold real press remains CALL; no SET.
    QTest.mousePress(widget, Qt.LeftButton, pos=QPoint(5, 5))
    QTest.qWait(800)
    assert sets == calls == []
    QTest.mouseRelease(widget, Qt.LeftButton, pos=QPoint(5, 5))
    assert calls == [42] and sets == []
    calls.clear()
    # Exceed the production interval, not a replacement test timer.
    QTest.mousePress(widget, Qt.LeftButton, pos=QPoint(5, 5))
    QTest.qWait(1200)
    assert sets == [42] and calls == []
    QTest.mouseRelease(widget, Qt.LeftButton, pos=QPoint(5, 5))
    assert sets == [42] and calls == []
    sets.clear()
    # Drag cancellation must retire the pending SET and late release.
    QTest.mousePress(widget, Qt.LeftButton, pos=QPoint(5, 5))
    widget._cancel_long_press()
    QTest.qWait(1200)
    widget._on_long_press()  # queued stale timeout
    QTest.mouseRelease(widget, Qt.LeftButton, pos=QPoint(5, 5))
    assert sets == calls == []
    widget.close()
# Role permission/confirmation remains independent of gesture duration.
for role in (OperatingMode.USER, OperatingMode.ADMIN):
    d = CallSetCommandPolicy().decide(role, InputType.LONG_PRESS,
        session_active=True, camera_available=True)
    assert d.allowed and d.action == CallSetAction.SET and d.requires_confirmation
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
