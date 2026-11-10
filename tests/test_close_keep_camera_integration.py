"""Exercise closeEvent with the real bus/controller/session service, not a copy."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("choice", ["keep", "off"])
def test_close_respects_camera_power_choice(choice):
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import os
with TemporaryDirectory() as root:
    for name in ('CONFIG', 'DATA', 'LOG', 'BACKUP', 'RUN', 'APP'):
        folder = Path(root) / name.lower()
        folder.mkdir()
        os.environ['KHPTZ_' + name + '_DIR'] = str(folder)
    import adapters.sim_mode as sim
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'sim.json'
    sim.activate()
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QCloseEvent
    from ui.main_window import MainWindow
    from adapters.fake_camera_port import FakeCameraPort
    from application.session_service import SessionService
    from domain.shutdown_intent import ShutdownIntent
    app = QApplication([])
    window = MainWindow()
    port = FakeCameraPort()
    service = SessionService(port)
    service._active = True
    window._session_svc = service
    window._controller._session = service
    window._camera_port = port
    window.session_active = True
    window._ask_shutdown_intent = lambda: ShutdownIntent.CHOICE
    event = QCloseEvent()
    window.closeEvent(event)
    thread = getattr(service, '_standby_thread', None)
    if thread is not None:
        thread.join(2)
    assert event.isAccepted()
    # CHECK_STANDBY
    assert service.active is False
    assert service.session_id is None
    window.hide()
    sim.deactivate()
'''
    script = script.replace('CHOICE', ('EXIT_KEEP_CAMERAS_ON' if choice == 'keep'
                                      else 'EXIT_AND_POWER_OFF_CAMERAS'))
    check = ('assert not any(call.startswith("standby:") for call in port.calls), port.calls'
             if choice == 'keep' else
             'assert "standby:cam1" in port.calls and "standby:cam2" in port.calls, port.calls')
    script = script.replace('# CHECK_STANDBY', check)
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
