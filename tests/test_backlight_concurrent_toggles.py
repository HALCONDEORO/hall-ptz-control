"""Two rapid clicks must toggle ON then OFF, not both send ON."""
import threading
from types import SimpleNamespace

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager


def test_concurrent_backlight_toggles_are_serialized():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    first_in_transport = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    sent = []
    results = []

    def confirmed(ip, visca_id, payload):
        sent.append(payload)
        if len(sent) == 1:
            first_in_transport.set()
            assert release_first.wait(2)
        else:
            second_entered.set()
        return True

    adapter._send_confirmed = confirmed
    first = threading.Thread(target=lambda: results.append(adapter.backlight_toggle('cam1')))
    second = threading.Thread(target=lambda: results.append(adapter.backlight_toggle('cam1')))
    first.start()
    assert first_in_transport.wait(2)
    second.start()
    try:
        # The second click must wait for the first confirmation before deciding
        # which target state to send. No real camera/network is used.
        assert not second_entered.wait(0.1)
    finally:
        release_first.set()
        first.join(2)
        second.join(2)
    assert not first.is_alive() and not second.is_alive()
    assert sent == ['01043302FF', '01043303FF']
    assert all(result.ok for result in results)
    assert adapter._backlight_on['cam1'] is False
    assert manager.backlight_on[1] is False


def test_waiting_toggle_does_not_hold_display_or_other_camera_lock():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81'),
                                           2: ('192.0.2.2', '82')})
    first_in_transport = threading.Event()
    release_first = threading.Event()
    other_completed = threading.Event()

    def confirmed(ip, visca_id, payload):
        if ip == '192.0.2.1':
            first_in_transport.set()
            assert release_first.wait(2)
        return True

    adapter._send_confirmed = confirmed
    first = threading.Thread(target=adapter.backlight_toggle, args=('cam1',))
    other = threading.Thread(target=lambda: (adapter.backlight_toggle('cam2'),
                                            other_completed.set()))
    first.start()
    assert first_in_transport.wait(2)
    try:
        other.start()
        assert other_completed.wait(1)
        adapter.update_camera_visca_id(1, '83')  # no display lock held by transport
    finally:
        release_first.set()
        first.join(2)
        other.join(2)
    assert not adapter._backlight_on.get('cam1', False)
    assert manager.backlight_on[2] is True
