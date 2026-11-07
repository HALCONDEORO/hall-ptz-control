"""Synchronous runtime subscribers may read the camera service they observe."""
import threading

import pytest

from application.camera_state_service import CameraStateService
from application.runtime_state_store import RuntimeStateStore


@pytest.mark.parametrize('action', ['on_camera_connected', 'on_reset'])
@pytest.mark.parametrize('reader', ['get_state', 'all_states'])
def test_store_subscriber_can_read_service_without_deadlock(action, reader):
    store = RuntimeStateStore(['cam1'])
    service = CameraStateService(['cam1'], runtime_state_store=store)
    observed = []
    errors = []

    def subscriber(snapshot):
        value = (service.get_state('cam1') if reader == 'get_state'
                 else service.all_states()['cam1'])
        observed.append(value.state.value)

    store.subscribe(subscriber)

    def update():
        try:
            getattr(service, action)('cam1')
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=update, daemon=True)
    thread.start()
    thread.join(timeout=1)
    assert not thread.is_alive(), 'synchronous subscriber deadlocked on camera state read'
    assert not errors
    assert observed == ['idle']
