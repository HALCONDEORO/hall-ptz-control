"""Real right clicks need explicit consent before dispatching SET."""
import os
from pathlib import Path
import subprocess
import sys


def test_right_click_requires_confirmation_on_real_widgets():
    script = r'''
from unittest.mock import patch
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox
from ui.widgets import GoButton, SpecialDragButton, PlatformPresetButton
app = QApplication([])
for make in (lambda: GoButton(42), lambda: SpecialDragButton(42, 'Seat'), PlatformPresetButton):
    widget = make()
    calls, saves = [], []
    widget.init_preset_actions(42, calls.append, saves.append)
    widget.show()
    for answer, expected in ((QMessageBox.No, []), (QMessageBox.Yes, [42])):
        with patch.object(QMessageBox, 'question', return_value=answer) as question:
            QTest.mouseClick(widget, Qt.RightButton)
        question.assert_called_once()
        assert question.call_args.args[-1] == QMessageBox.No
        assert saves == expected, (type(widget).__name__, saves)
        assert calls == []
        assert not widget._long_press_timer.isActive()
    QTest.mouseClick(widget, Qt.LeftButton)
    assert calls == [42]
    assert saves == [42]
    widget.close()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
