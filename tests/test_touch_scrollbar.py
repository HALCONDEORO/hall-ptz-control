"""Run Qt-sensitive checks in a fresh interpreter, away from suite stubs."""
import os
from pathlib import Path
import subprocess
import sys

if os.environ.get('KHPTZ_ISOLATED_TEST_TOUCH_SCROLLBAR_PY') != '1':
    def test_isolated_qt_regressions():
        env = dict(os.environ, KHPTZ_ISOLATED_TEST_TOUCH_SCROLLBAR_PY='1', QT_QPA_PLATFORM='offscreen')
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(Path(__file__).resolve()),
             '-q', '-o', 'addopts='], env=env, capture_output=True, text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
else:
    """Verify the actual Qt scrollbar touch target, not just the QSS string."""
    def test_vertical_scrollbar_is_wide_and_has_usable_handle():
        from conftest import ensure_real_qt
        ensure_real_qt()
        from PyQt5.QtWidgets import QApplication, QScrollArea, QWidget
        from ui.styles import touch_scrollbar_qss, TOUCH_SCROLLBAR_WIDTH
        app = QApplication.instance() or QApplication([])
        area = QScrollArea()
        area.setStyleSheet(touch_scrollbar_qss())
        area.resize(420, 360)
        content = QWidget()
        content.resize(300, 1400)
        area.setWidget(content)
        area.show()
        app.processEvents()
        assert area.verticalScrollBar().width() == TOUCH_SCROLLBAR_WIDTH
        assert area.verticalScrollBar().sizeHint().width() == TOUCH_SCROLLBAR_WIDTH
        area.close()
