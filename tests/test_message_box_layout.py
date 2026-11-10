"""Run Qt-sensitive checks in a fresh interpreter, away from suite stubs."""
import os
from pathlib import Path
import subprocess
import sys

if os.environ.get('KHPTZ_ISOLATED_TEST_MESSAGE_BOX_LAYOUT_PY') != '1':
    def test_isolated_qt_regressions():
        env = dict(os.environ, KHPTZ_ISOLATED_TEST_MESSAGE_BOX_LAYOUT_PY='1', QT_QPA_PLATFORM='offscreen')
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(Path(__file__).resolve()),
             '-q', '-o', 'addopts='], env=env, capture_output=True, text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
else:
    """Long custom labels must fit at real fallback fonts and larger Pi scaling."""
    import pytest


    @pytest.mark.parametrize('font_px', [13, 20, 26])
    def test_custom_message_buttons_fit_real_text(font_px):
        from conftest import ensure_real_qt
        ensure_real_qt()
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from ui.message_box_layout import fit_message_box_buttons
        app = QApplication.instance() or QApplication([])
        box = QMessageBox()
        box.setText('How do you want to close the application?')
        labels = ['Keep cameras on', 'Power off cameras', 'Cancel']
        for label in labels:
            box.addButton(label, QMessageBox.ActionRole)
        box.setStyleSheet(f'QPushButton {{font-size:{font_px}px; padding:7px 16px;}}')
        fit_message_box_buttons(box)
        box.show()
        app.processEvents()
        for button in box.buttons():
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 48
            assert button.width() >= button.sizeHint().width()
            assert button.height() >= button.fontMetrics().height() + 20
        box.close()
