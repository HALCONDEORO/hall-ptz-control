"""Missing cameras must never connect to localhost or run display queries."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from ui.camera_worker_startup import start_configured_camera_workers
from ptz.visca.manager import CameraManager
from adapters.visca_camera_adapter import ViscaCameraAdapter


@pytest.mark.parametrize('ips,expected', [(('', ''), []),
    (('192.0.2.11', ''), ['192.0.2.11']),
    (('', '192.0.2.12'), ['192.0.2.12']),
    (('127.0.0.1', '127.0.0.2'), ['127.0.0.1', '127.0.0.2'])])
def test_startup_only_creates_configured_workers(ips, expected):
    manager = Mock()
    manager.ip_for_key.side_effect = lambda key: ips[key - 1]
    start_configured_camera_workers(manager)
    assert [call.args[0] for call in manager.worker.call_args_list] == expected


@pytest.mark.parametrize('method', ['refresh_zoom_display', 'async_refresh_ae_mode'])
@pytest.mark.parametrize('ip', ['', ' '])
def test_missing_display_endpoint_is_noop_before_cache_and_no_query_thread(method, ip):
    # Deliberately retain old manager endpoints: an adapter display snapshot can
    # be empty before/after runtime repoint. cam_key('') would raise here.
    manager = CameraManager(SimpleNamespace(ip='192.0.2.11', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: (ip, '81'), 2: ('192.0.2.12', '82')})
    callback = Mock()
    with patch('adapters.visca_camera_adapter.threading.Thread') as thread:
        getattr(adapter, method)(1, callback)
    thread.assert_not_called()
    callback.assert_not_called()
    assert manager._workers == {}


def test_main_window_wires_guarded_startup_not_unconditional_worker_calls():
    from pathlib import Path
    source = Path('ui/main_window.py').read_text()
    assert 'start_configured_camera_workers(self._cameras)' in source
    assert 'self._cameras.worker(self._cameras.ip_for_key(' not in source
