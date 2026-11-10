"""Run pixel checks in a fresh interpreter, safe under pytest --forked."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('initial,target', [('call', 'set'), ('set', 'call')])
@pytest.mark.parametrize('ticks', [1, 7, 13])
def test_reversing_fade_preserves_pixels(initial, target, ticks):
    script = r'''
import sys
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QWidget
from ui.auditorium_overlay import AuditoriumOverlay

_APP = QApplication([])
initial, target, ticks = sys.argv[1], sys.argv[2], int(sys.argv[3])
def check():
    parent = QWidget()
    parent.resize(600, 400)
    palette = parent.palette()
    palette.setColor(QPalette.Window, QColor('#526778'))
    parent.setPalette(palette)
    parent.setAutoFillBackground(True)
    overlay = AuditoriumOverlay(parent)
    overlay.set_mode(initial)
    overlay._timer.stop()
    overlay._blend = 1.0
    parent.show()
    _APP.processEvents()
    try:
        overlay.set_mode(target)
        overlay._timer.stop()
        for _ in range(ticks):
            overlay._tick()
        _APP.processEvents()
        before = parent.grab().toImage()
        overlay.set_mode(initial)
        overlay._timer.stop()
        _APP.processEvents()
        after = parent.grab().toImage()
        # Check both a dot and a point between dots, including rounding tolerance.
        for x, y in [(12, 12), (100, 100)]:
            a, b = before.pixelColor(x, y), after.pixelColor(x, y)
            assert max(abs(a.red()-b.red()), abs(a.green()-b.green()),
                       abs(a.blue()-b.blue())) <= 1
        assert overlay._mode == initial
        for _ in range(15):
            overlay._tick()
        assert overlay._blend == 1.0
        assert not overlay._timer.isActive()
    finally:
        parent.close()

check()
'''
    result = subprocess.run(
        [sys.executable, '-c', script, initial, target, str(ticks)],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
