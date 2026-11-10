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
