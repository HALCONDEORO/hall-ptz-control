"""ATEM handshake is not proof that program polling works."""
import os
from pathlib import Path
import subprocess
import sys


def _run(script):
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_valid_poll_verifies_first_read_and_same_program_recovery():
    _run(r'''
from types import SimpleNamespace
from unittest.mock import patch
from PyQt5.QtCore import QCoreApplication, Qt
from adapters.atem_monitor import ATEMMonitor
from domain.atem_state import ATEMState
app = QCoreApplication([])
monitor = ATEMMonitor('192.0.2.1')
verified, changes = [], []
monitor.program_verified.connect(verified.append, Qt.DirectConnection)
monitor.program_changed.connect(changes.append, Qt.DirectConnection)
monitor._emit_state(ATEMState.CONNECTED)
assert verified == []
class Inputs:
    count = 0
    def __getitem__(self, index):
        self.count += 1
        if self.count == 2:
            raise OSError('poll unavailable')
        return SimpleNamespace(videoSource=3)
with patch.object(monitor, 'isInterruptionRequested', side_effect=[False]*4+[True]), patch('adapters.atem_monitor.time.sleep'), patch.object(monitor, '_poll_pip'):
    monitor._poll_loop(SimpleNamespace(programInput=Inputs()))
assert verified == [3, 3], verified
assert changes == [3], changes
''')


def test_retired_monitor_verification_cannot_open_current_ui():
    _run(r'''
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PyQt5.QtCore import QCoreApplication, Qt, QObject, pyqtSignal
from ui.atem_operational import accept_program_verification, atem_operational
from domain.atem_state import ATEMState
app = QCoreApplication([])
class Source(QObject):
    verified = pyqtSignal(int)
class Receiver(QObject):
    def receive(self, value):
        accept_program_verification(self, value)
old, current = Source(), Source()
current.state = ATEMState.CONNECTED
window = Receiver()
window._atem_monitor = current
window._atem_state = ATEMState.CONNECTED
window._atem_verified_monitor = None
window._atem_is_configured = lambda: True
window.atem_state_changed = Mock()
window._update_atem_button = Mock()
window._right_panel = Mock()
old.verified.connect(window.receive, Qt.QueuedConnection)
current.verified.connect(window.receive, Qt.QueuedConnection)
old.verified.emit(3)
app.processEvents()
assert not atem_operational(window)
current.verified.emit(3)
app.processEvents()
assert atem_operational(window)
window._right_panel.set_atem_program.assert_called_once_with(3)
window.atem_state_changed.emit.assert_called_once_with(ATEMState.CONNECTED)
window._atem_state = ATEMState.DISCONNECTED
assert not atem_operational(window)
''')


def test_bad_program_reads_never_verify_handshake():
    _run(r'''
from unittest.mock import Mock, patch
from PyQt5.QtCore import QCoreApplication, Qt
from adapters.atem_monitor import ATEMMonitor
from domain.atem_state import ATEMState
app = QCoreApplication([])
monitor = ATEMMonitor('192.0.2.1')
verified = []
monitor.program_verified.connect(verified.append, Qt.DirectConnection)
monitor._emit_state(ATEMState.CONNECTED)
atem = Mock()
atem.programInput = []
with patch.object(monitor, 'isInterruptionRequested', side_effect=[False, False, True]), patch('adapters.atem_monitor.time.sleep'), patch.object(monitor, '_poll_pip'):
    monitor._poll_loop(atem)
assert verified == []
assert monitor.state == ATEMState.ERROR
''')


def test_main_window_wires_verification_and_clears_it_on_disconnect():
    _run(r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
import adapters.sim_mode as sim
from domain.atem_state import ATEMState
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    from adapters.atem_monitor import ATEMMonitor
    window = MainWindow()
    monitor = ATEMMonitor('192.0.2.1')
    old = ATEMMonitor('192.0.2.2')
    window._atem_monitor = monitor
    window._atem_is_configured = lambda: True
    window._update_atem_button = Mock()
    window._right_panel.set_atem_program = Mock()
    bindings = window._atem_monitor_signal_bindings(monitor)
    assert any(signal == monitor.program_verified and slot == window._on_atem_program_verified for signal, slot in bindings)
    monitor.program_verified.connect(window._on_atem_program_verified, Qt.QueuedConnection)
    old.program_verified.connect(window._on_atem_program_verified, Qt.QueuedConnection)
    monitor._emit_state(ATEMState.CONNECTED)
    window._on_atem_state_changed(ATEMState.CONNECTED)
    assert not window.atem_operational()
    monitor.program_verified.emit(3)
    app.processEvents()
    assert window.atem_operational()
    window._on_atem_state_changed(ATEMState.ERROR)
    assert not window.atem_operational()
    assert window._atem_verified_monitor is None
    monitor._emit_state(ATEMState.CONNECTED)
    window._on_atem_state_changed(ATEMState.CONNECTED)
    assert not window.atem_operational()
    old.program_verified.emit(3)
    app.processEvents()
    assert not window.atem_operational()
    monitor.program_verified.emit(3)
    app.processEvents()
    assert window.atem_operational()
    window._atem_is_configured = lambda: False
    assert not window.atem_operational()
    window.hide()
    sim.deactivate()
''')
