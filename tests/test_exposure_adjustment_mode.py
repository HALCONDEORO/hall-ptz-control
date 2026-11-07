"""Exposure adjustment follows the observed AE mode, not a fixed opcode."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager


@pytest.mark.parametrize('direction,opcode', [('up', '02'), ('down', '03')])
@pytest.mark.parametrize('mode', ['auto', 'manual', 'bright'])
def test_exposure_command_uses_observed_mode(mode, direction, opcode):
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    manager.ae_mode[1] = mode
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    adapter._send_confirmed = Mock(return_value=True)
    assert getattr(adapter, 'brightness_' + direction)('cam1').ok
    commands = [call.args[2] for call in adapter._send_confirmed.call_args_list]
    assert commands == (['01043E02FF', '01040E' + opcode + 'FF'] if mode == 'auto'
                        else ['01040D' + opcode + 'FF'])


def test_failed_expcomp_enable_does_not_send_adjustment():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    adapter._send_confirmed = Mock(return_value=False)
    assert not adapter.brightness_up('cam1').ok
    assert [call.args[2] for call in adapter._send_confirmed.call_args_list] == ['01043E02FF']


def test_reconfigured_target_after_enable_does_not_receive_step():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})

    def enable(*args):
        adapter.update_camera_ip(1, '192.0.2.3')
        return True

    adapter._send_confirmed = Mock(side_effect=enable)
    assert not adapter.brightness_up('cam1').ok
    assert adapter._send_confirmed.call_count == 1


def test_unknown_ae_mode_does_not_send_a_guessed_command():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    manager.ae_mode[1] = 'unsupported'
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    adapter._send_confirmed = Mock()
    assert not adapter.brightness_up('cam1').ok
    adapter._send_confirmed.assert_not_called()
