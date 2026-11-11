"""Exercise the pinned upstream library, not permissive API mocks.

All datagrams stay on a local UDP receiver. No ATEM address is contacted and
command tests do not start library communication threads. The lifecycle test
starts and stops real library threads against that same loopback receiver. Optional dependency must be
installed from requirements-atem.txt; CI runs this file in a dedicated step.
"""
import inspect
from importlib.metadata import version
import socket

import pytest

PyATEMMax = pytest.importorskip('PyATEMMax')

from adapters.atem_monitor import ATEMMonitor
from adapters.atem_values import source_number
from adapters.atem_write_adapter import ATEMWriteAdapter
from domain.atem_state import ATEMState


@pytest.fixture
def real_switcher():
    assert version('PyATEMMax') == '1.0b9'
    switcher = PyATEMMax.ATEMMax()
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(('127.0.0.1', 0))
    receiver.settimeout(0.2)
    switcher._udp._socket.connect(receiver.getsockname())
    switcher._udp.connected = True
    switcher.connected = True
    adapter = ATEMWriteAdapter('192.0.2.1')
    adapter._atem = switcher
    adapter._connected = True
    try:
        yield switcher, adapter, receiver
    finally:
        switcher.connected = False
        switcher._udp._socket.close()
        receiver.close()


def test_pinned_lifecycle_signatures_and_bounded_wait(real_switcher):
    switcher, _, _ = real_switcher
    inspect.signature(switcher.connect).bind('192.0.2.1')
    inspect.signature(switcher.waitForConnection).bind(timeout=3)
    inspect.signature(switcher.disconnect).bind()
    assert switcher.waitForConnection(timeout=0.001) is False
    switcher.disconnect()  # inert without starting library communication threads


@pytest.mark.parametrize('command,wire_name,target', [
    ('cut', b'DCut', 0), ('auto', b'DAut', 0),
    ('set_preview_input', b'CPvI', 2),
])
def test_real_command_serialization_on_loopback(real_switcher, command, wire_name, target):
    switcher, adapter, receiver = real_switcher
    result = getattr(adapter, command)(2) if command == 'set_preview_input' else getattr(adapter, command)()
    assert result.ok
    datagram = receiver.recv(2048)
    assert datagram[16:20] == wire_name
    assert datagram[20] == 0  # M/E 1, zero-based on wire
    assert int.from_bytes(datagram[22:24], 'big') == target
    assert switcher.started is False


def test_real_program_preview_status_and_test_connection(real_switcher):
    switcher, adapter, _ = real_switcher
    switcher.programInput[0].videoSource = switcher.atem.videoSources[1]
    switcher.previewInput[0].videoSource = switcher.atem.videoSources[2]
    assert adapter.get_program_input() == 1
    assert adapter.get_preview_input() == 2
    assert adapter.test_connection().ok
    status = adapter.get_status()
    assert status.connected and status.program_input == 1 and status.preview_input == 2


def test_real_monitor_program_and_input_name_reads(real_switcher):
    from PyQt5.QtCore import Qt
    switcher, _, _ = real_switcher
    class OnePollMonitor(ATEMMonitor):
        remaining = 1

        def isInterruptionRequested(self):
            self.remaining -= 1
            return self.remaining < 0

    monitor = OnePollMonitor('192.0.2.1')
    switcher.programInput[0].videoSource = switcher.atem.videoSources[2]
    switcher.inputProperties[2].longName = 'Platform actual API'
    assert monitor._read_input_names(switcher, PyATEMMax)[2] == 'Platform actual API'
    program = []
    monitor.program_changed.connect(program.append, Qt.DirectConnection)
    monitor._state = ATEMState.CONNECTED
    monitor._poll_loop(switcher)
    assert program == [2]


def test_real_pip_api_gap_is_explicit_and_does_not_write_keyers(real_switcher):
    switcher, adapter, receiver = real_switcher
    assert not hasattr(switcher, 'pictureInPicture')
    assert not hasattr(switcher, 'setPIPEnabled')
    assert not hasattr(switcher, 'setPictureInPictureEnabled')
    assert callable(switcher.setKeyerOnAirEnabled)
    switcher.keyer[0][0].onAir.enabled = True
    switcher.keyer[0][0].fillSource = switcher.atem.videoSources[2]
    assert source_number(switcher.keyer[0][0].fillSource) == 2
    result = adapter.set_pip_enabled(True)
    assert not result.ok and result.error_code == 'API_NOT_FOUND'
    assert adapter._connected  # unsupported PiP must not break other commands
    with pytest.raises(socket.timeout):
        receiver.recv(2048)  # no keyer command may be guessed


def test_real_connect_wait_disconnect_lifecycle_stays_on_loopback():
    switcher = PyATEMMax.ATEMMax()
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(('127.0.0.1', 0))
    receiver.settimeout(1)
    switcher._udp.atem.UDPPort = receiver.getsockname()[1]
    try:
        switcher.connect('127.0.0.1')
        comms, events = switcher._commsThread, switcher._eventThread
        packet, sender = receiver.recvfrom(2048)
        assert sender[0] == '127.0.0.1' and packet
        assert switcher.waitForConnection(timeout=0.02) is False
        switcher.disconnect()
        assert not comms.is_alive() and not events.is_alive()
        assert not switcher.started
    finally:
        switcher.disconnect()
        switcher._udp._socket.close()
        receiver.close()
