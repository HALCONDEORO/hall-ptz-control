"""Exercise real preset widgets rather than a copy of the interaction logic."""
import os
from pathlib import Path
import subprocess
import sys


def test_right_click_sets_once_on_real_preset_widgets():
    script = r'''
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from ui.widgets import GoButton, SpecialDragButton, PlatformPresetButton
app = QApplication([])
for make in (lambda: GoButton(42), lambda: SpecialDragButton(42, 'Seat'), PlatformPresetButton):
    widget = make()
    calls, saves = [], []
    widget.init_preset_actions(42, calls.append, saves.append)
    widget.show()
    QTest.mouseClick(widget, Qt.RightButton)
    assert saves == [42], (type(widget).__name__, saves)
    assert calls == []
    assert not widget._long_press_timer.isActive()
    # Context-menu delivery must not duplicate the SET. A later tap still calls.
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
