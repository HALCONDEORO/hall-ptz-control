# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Check the packaged background through Qt's production JPEG decoder."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_light_background_decodes_and_keeps_platform_separate():
    code = '''
from PyQt5.QtGui import QImage
image = QImage("ui/khptz_background.jpg")
assert not image.isNull()
assert (image.width(), image.height()) == (1920, 1080)
def close(x, y, expected):
    color = image.pixelColor(x, y)
    assert all(abs(a-b) <= 4 for a,b in zip(color.getRgb()[:3], expected)), (x,y,color.name())
platform = (169,191,210)
seats = (201,217,230)
# Three central platform icons and their labels stay on the darker tone.
for x in (562,744,938):
    close(x, 60, platform)
    close(x, 133, platform)
# Both upper wheelchair positions remain in the auditorium, not the platform.
for x in (170,1240):
    close(x, 125, seats)
    close(x, 175, seats)
# Borderless diagonal chamfers: samples on either side of each diagonal.
close(395, 110, platform)
close(395, 135, seats)
close(1080, 110, platform)
close(1080, 135, seats)
close(744, 170, seats)
close(744, 600, seats)
close(744, 1030, seats)
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
