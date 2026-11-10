"""Endpoint retirement and shutdown cannot spawn replacement orphan sessions."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from ptz.visca.manager import CameraManager
from adapters.visca_camera_adapter import ViscaCameraAdapter


@contextmanager
def worker_factory():
    # Some legacy tests reload the manager module during collection.
    factory = Mock()
    with patch.dict(CameraManager.worker.__globals__, CameraWorker=factory):
        yield factory


def rig():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.11', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    return manager, ViscaCameraAdapter(manager, {1: ('192.0.2.11', '81'),
                                               2: ('192.0.2.12', '82')})


@pytest.mark.parametrize('endpoint', ['', '192.0.2.99'])
def test_unknown_or_empty_endpoint_never_constructs_worker(endpoint):
    manager, _ = rig()
    with worker_factory() as factory:
        with pytest.raises(ValueError):
            manager.worker(endpoint)
        factory.assert_not_called()


def test_captured_query_and_commands_cannot_recreate_retired_endpoint():
    manager, adapter = rig()
    with worker_factory() as factory:
        manager.update_camera_ip(1, '192.0.2.21')
        factory.reset_mock()
        assert adapter._query_response('192.0.2.11', '81', bytes.fromhex('81090447ff')) == b''
        assert adapter._send_confirmed('192.0.2.11', '81', '01040002ff') is False
        assert adapter._send_queued('cam1', '192.0.2.11', bytes.fromhex('8101040700ff')) is False
        factory.assert_not_called()
        assert '192.0.2.11' not in manager._workers


def test_stop_all_is_terminal_even_for_registered_endpoint():
    manager, adapter = rig()
    old = Mock()
    manager._workers['192.0.2.11'] = old
    manager.stop_all()
    with worker_factory() as factory:
        assert adapter._query_response('192.0.2.11', '81', bytes.fromhex('81090447ff')) == b''
        assert adapter.stop_move('cam1').ok is False
        manager.stop_all()
        factory.assert_not_called()
    old.stop.assert_called_once()
    assert manager._workers == {}


def test_reassignment_overtaken_during_old_worker_stop_never_spawns_intermediate():
    manager, _ = rig()
    old = Mock()
    manager._workers['192.0.2.11'] = old
    old.stop.side_effect = lambda: manager.update_camera_ip(1, '192.0.2.31')
    with worker_factory() as factory:
        manager.update_camera_ip(1, '192.0.2.21')
        factory.assert_called_once_with('192.0.2.31')
    assert set(manager._workers) == {'192.0.2.31'}


def test_explicit_shutdown_standby_precedes_terminal_worker_retirement():
    from pathlib import Path
    source = Path('ui/main_window.py').read_text()
    close = source[source.index('    def closeEvent('):]
    assert close.index('self._camera_port.standby("cam2")') < close.index('self._cameras.stop_all()')
