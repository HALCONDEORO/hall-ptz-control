"""Synthetic visibility checks using the real-Qt collection guard."""
from types import SimpleNamespace

import pytest


@pytest.fixture
def page():
    from conftest import ensure_real_qt, is_poisoned_by_qt_stub
    ensure_real_qt()
    from PyQt5.QtWidgets import QApplication
    from ui.setup_wizard.pages import PasswordsPage
    if is_poisoned_by_qt_stub(PasswordsPage):
        pytest.skip("PasswordsPage was imported under a Qt stub; run in isolation")
    app = QApplication.instance() or QApplication([])
    widget = PasswordsPage(SimpleNamespace(answers=SimpleNamespace()))
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def fields(page):
    return [page.entry, page.entry_confirm, page.admin, page.admin_confirm]


def test_independent_keyboard_toggles_and_reset(page):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QLineEdit
    widgets = fields(page)
    assert all(f.echoMode() == QLineEdit.Password for f in widgets)
    for index, button in enumerate(page.visibility_buttons):
        assert button.minimumWidth() >= 44 and button.minimumHeight() >= 44
        assert button.accessibleName().startswith('Show ')
        assert not button.icon().isNull()
        widgets[index].setText('synthetic-only')
        button.setFocus()
        QTest.keyClick(button, Qt.Key_Space)
        assert [f.echoMode() for f in widgets] == [
            QLineEdit.Normal if i == index else QLineEdit.Password for i in range(4)]
        assert button.accessibleName().startswith('Hide ')
        button.click()
        assert widgets[index].text() == 'synthetic-only'
        assert all(f.echoMode() == QLineEdit.Password for f in widgets)
    page.visibility_buttons[0].click()
    page.hide()
    assert all(f.echoMode() == QLineEdit.Password for f in widgets)
    page.initializePage()
    assert all(f.text() == 'synthetic-only' for f in widgets)


def test_validation_unchanged(page):
    for button in page.visibility_buttons:
        button.click()
    assert not page.validatePage()
    assert page.error_text() == 'Enter an operator password.'
    page.entry.setText('synthetic-operator')
    assert not page.validatePage()
    page.entry_confirm.setText('synthetic-operator')
    assert not page.validatePage()
    page.admin.setText('synthetic-admin')
    assert not page.validatePage()
    page.admin_confirm.setText('synthetic-admin')
    assert page.validatePage()
    assert page.answers.entry_password == 'synthetic-operator'
    assert page.answers.admin_password == 'synthetic-admin'
    for button in page.visibility_buttons:
        button.click()
    assert page.validatePage()
    page.admin.setText('synthetic-operator')
    page.admin_confirm.setText('synthetic-operator')
    assert not page.validatePage()
    assert page.error_text() == 'Use different passwords for operator and administrator.'
