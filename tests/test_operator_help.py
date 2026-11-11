"""Real Qt operator-help flow, isolated from suite stubs and hardware."""
import os
from pathlib import Path
import subprocess
import sys


def test_user_help_flow_uses_full_stop_route_without_other_commands():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    from domain.call_set_policy import OperatingMode
    from core.events import EventType
    window = MainWindow()
    window._access_mode_svc.set_mode(OperatingMode.USER)
    window.show()
    app.processEvents()
    entry = window._operator_help
    assert entry.button.width() >= 44 and entry.button.height() >= 44
    assert not entry.button.isHidden() and entry.button.isEnabled()
    admin = window._right_panel._btn_enter_admin
    assert entry.button.y() > admin.y() + admin.height()
    calls = []
    window._bus = Mock()
    window._bus.emit.side_effect = lambda *a, **k: calls.append(('emit', a, k))
    service = Mock()
    service.stop_all_cameras.side_effect = lambda: calls.append(('svc',)) or Mock(ok=True)
    window._runtime_safety_svc = service
    window._cameras = Mock()
    window._cameras.ip_for_key.side_effect = lambda n: 'synthetic-' + str(n)
    window._cameras.is_connected.return_value = False
    with patch.object(QMessageBox, 'question', side_effect=AssertionError('No confirmation')):
        entry.button.click()
        app.processEvents()
        dialog = entry.dialog
        assert calls == []  # opening never issues camera commands
        QTest.keyClick(dialog, Qt.Key_Return)
        assert calls == []  # STOP is not an implicit default button
        dialog.status_button.click()
        assert 'Not connected / unknown' in dialog.body.text()
        dialog.back_button.click()
        assert dialog.stop_button.isEnabled() and not window.session_active
        dialog.stop_button.click()
        assert [c[2]['camera'] for c in calls if c[0] == 'emit'] == [1, 2]
        assert all(c[1][0] == EventType.CAMERA_STOP for c in calls if c[0] == 'emit')
        assert calls[-1] == ('svc',)
        service.stop_all_cameras.assert_called_once_with()
        assert 'STOP sent' in dialog.feedback.text() and 'not confirmed' in dialog.feedback.text()
        service.stop_all_cameras.side_effect = RuntimeError('synthetic transport failure')
        dialog.stop_button.click()
        assert 'Could not confirm' in dialog.feedback.text()
        service.stop_all_cameras.side_effect = lambda: Mock(ok=False)
        dialog.stop_button.click()
        assert 'Could not confirm' in dialog.feedback.text()
        del window._runtime_safety_svc
        dialog.stop_button.click()
        assert 'Could not confirm' in dialog.feedback.text()
        dialog.close_button.click()
        assert not dialog.isVisible()
        entry.button.click()
        assert entry.dialog is dialog and 'Check the cameras' in dialog.feedback.text()
        dialog.resize(800, 480)
        app.processEvents()
        assert dialog.stop_button.geometry().bottom() < dialog.height()
        assert dialog.close_button.width() >= 44 and dialog.close_button.height() >= 44
        for topic in dialog.topic_buttons:
            assert topic.height() >= 44
            assert topic.visibleRegion().boundingRect().height() >= 44
        for number, topic in enumerate(dialog.topic_buttons):
            topic.click()
            app.processEvents()
            assert dialog.pages.currentIndex() == 1
            assert topic.text().split('   >')[0] in dialog.body.text()
            assert dialog.stop_button.isVisible() and dialog.stop_button.isEnabled()
            assert dialog.close_button.isVisible()
            assert dialog.scroll.horizontalScrollBar().maximum() == 0
            if dialog.scroll.verticalScrollBar().maximum() > 0:
                assert dialog.scroll.verticalScrollBar().width() >= 32
            dialog.back_button.click()
        dialog.status_button.click()
        app.processEvents()
        dialog.scroll.verticalScrollBar().setValue(dialog.scroll.verticalScrollBar().maximum())
        app.processEvents()
        assert dialog.body.visibleRegion().boundingRect().height() > 0
        dialog.close()
    # Existing ADMIN STOP ALL visibility and Settings permissions stay unchanged.
    buttons = window._right_panel._container.findChildren(QPushButton)
    stop = next(b for b in buttons if b.text() == 'STOP ALL')
    assert stop.isHidden()
    window._access_mode_svc.set_mode(OperatingMode.ADMIN)
    assert not stop.isHidden()
    window._access_mode_svc.set_mode(OperatingMode.USER)
    assert stop.isHidden()
    window.hide()
    sim.deactivate()
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
