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
