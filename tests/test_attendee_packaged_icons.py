# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Attendee actions must not depend on OS emoji fonts (including Bullseye).

Use a fresh interpreter because other legacy tests stub Qt modules globally.
"""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_attendee_icons_render_and_labels_stay_readable():
    code = '''
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from ui.icon_loader import get_svg_icon
from ui.names_panel import NamesPanel
app = QApplication([])
app.setFont(QFont("DejaVu Sans", 10))
for name in ("attendees", "search", "add", "undo", "refresh"):
    icon = get_svg_icon(name)
    assert not icon.isNull(), name
    pixmap = icon.pixmap(24, 24)
    assert not pixmap.isNull(), name
    image = pixmap.toImage()
    assert any(image.pixelColor(x, y).alpha() for x in range(24) for y in range(24)), name
panel = NamesPanel(["Example"], lambda *a: None, lambda: None)
assert panel._title.text() == "Attendees  (0/1 seated)"
assert not panel._title_icon.pixmap().isNull()
assert panel._search.placeholderText().isascii()
assert panel._search.accessibleName() == "Search attendees"
assert panel._search.actions()
assert [b.text() for b in panel._edit_buttons] == ["Add", "Undo last assignment", "Bring All Back"]
assert all(not b.icon().isNull() and b.accessibleName() for b in panel._edit_buttons)
assert all(not b.isEnabled() for b in panel._edit_buttons)
panel.set_edit_mode(True)
assert all(b.isEnabled() for b in panel._edit_buttons)
panel.set_assigned({"Example"})
assert panel._title.text() == "Attendees  (1/1 seated)"
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_svg_loader_missing_asset_fallback_and_strict_mode():
    code = '''
from PyQt5.QtWidgets import QApplication
from ui import icon_loader
app = QApplication([])
assert icon_loader.get_svg_icon("__missing_attendee_icon__").isNull()
icon_loader._STRICT = True
try:
    icon_loader.get_svg_icon("__missing_attendee_icon__")
except FileNotFoundError:
    pass
else:
    raise AssertionError("strict mode must detect missing assets")
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
