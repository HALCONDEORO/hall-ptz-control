"""Regression: starting a seat-name drag must cancel a pending long-press SET.

A GoButton left-press starts BOTH the drag tracking (_drag_start_pos) and the
long-press QTimer. QDrag.exec_() runs a nested event loop, so a drag lasting
more than LONG_PRESS_MS used to fire _on_long_press mid-drag and dispatch a
SET (preset overwrite) while the operator was only moving a name.
"""
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
def go_button(request):
    if getattr(request.node, "_preset_child_passed", False):
        yield None
        return
    ensure_real_qt()
    from PyQt5.QtWidgets import QApplication
    from ui.widgets import GoButton
    app = QApplication.instance() or QApplication([])
    calls, sets = [], []
    GoButton.set_call_mode(False)  # SET mode: seat names are draggable
    button = GoButton(5)
    button.init_preset_actions(5, calls.append, sets.append)
    button._long_press_timer.setInterval(20)
    button.set_name("Ana", emit_signal=False)
    button.show()
    app.processEvents()
    yield app, button, calls, sets
    button.close()
    GoButton.set_call_mode(True)


def test_drag_start_cancels_pending_long_press(go_button, monkeypatch):
    if go_button is None:
        return  # parent process: the fresh child already asserted
    app, button, calls, sets = go_button
    from PyQt5 import QtGui
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication

    def drag_move(target, pos):
        """MouseMove carrying LeftButton in buttons(); QTest.mouseMove sends none."""
        event = QMouseEvent(
            QEvent.MouseMove, QPointF(pos), QPointF(target.mapToGlobal(pos)),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )
        QApplication.sendEvent(target, event)

    class FakeDrag:
        """Stands in for QDrag so no real OS drag session starts."""

        def __init__(self, parent):
            self._mime = None

        def setMimeData(self, mime):
            self._mime = mime

        def exec_(self, _actions):
            return Qt.CopyAction  # abandoned drag: the name stays put

    monkeypatch.setattr(QtGui, "QDrag", FakeDrag)

    QTest.mousePress(button, Qt.LeftButton, pos=QPoint(5, 5))
    assert button._long_press_timer.isActive()

    far = 5 + QApplication.startDragDistance() + 30
    drag_move(button, QPoint(far, 5))

    # The drag must cancel the pending SET, not let it fire mid-drag.
    assert not button._long_press_timer.isActive()
    QTest.qWait(60)  # 3x the long-press interval
    app.processEvents()
    assert sets == []
    assert calls == []
    assert button.assigned_name == "Ana"

    QTest.mouseRelease(button, Qt.LeftButton, pos=QPoint(far, 5))
    app.processEvents()
    assert calls == []  # release after a cancelled press must not CALL either
    assert sets == []
