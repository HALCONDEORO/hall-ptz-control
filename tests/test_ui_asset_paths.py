"""Packaged SVGs must not depend on the shell working directory."""
import os
from pathlib import Path
import subprocess
import sys


def test_special_svg_assets_load_outside_ui_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = '''from PyQt5.QtWidgets import QApplication
from ui.seat_builder import _load_svg_pixmap
from ui import widgets
app=QApplication([])
for name in ('second_room.svg','library.svg'):
    pixmap=_load_svg_pixmap(None,name,40,40)
    assert pixmap is not None and not pixmap.isNull()
assert widgets._SEAT_SVG_EXISTS
assert str(widgets._UI_ASSET_DIR) in widgets._SEAT_SVG_BG
'''
    env = dict(os.environ, PYTHONPATH=str(root), QT_QPA_PLATFORM='offscreen')
    subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env, check=True)
