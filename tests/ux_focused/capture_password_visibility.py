"""QT_QPA_PLATFORM=offscreen python3 tests/ux_focused/capture_password_visibility.py OUTPUT.png"""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt5.QtWidgets import QApplication
from ui.setup_wizard.pages import PasswordsPage

app = QApplication([])
page = PasswordsPage(SimpleNamespace(answers=SimpleNamespace()))
for field in (page.entry, page.entry_confirm, page.admin, page.admin_confirm):
    field.setText('synthetic-example')
page.visibility_buttons[0].click()
page.resize(720, 480)
page.show()
app.processEvents()
if not page.grab().save(sys.argv[1]):
    raise SystemExit('Could not save screenshot')
