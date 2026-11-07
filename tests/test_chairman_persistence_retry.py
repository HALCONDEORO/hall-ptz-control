"""A camera-confirmed but unpersisted mapping must remain pending on retry."""
from unittest.mock import Mock, patch

import pytest

from application.preset_service import PresetService
from core.controller import Controller
from core.events import Event, EventType
from core.state import SystemState


@pytest.mark.parametrize('retry_succeeds', [False, True])
def test_retries_disk_save_before_reporting_preset_saved(retry_succeeds):
    with patch('application.preset_service.load_chairman_presets', return_value={}), \
         patch('application.preset_service.save_chairman_presets',
               side_effect=[False, retry_succeeds]) as save:
        presets = PresetService()
        state = SystemState()
        state.session.active = True
        bus, port = Mock(), Mock()
        port.save_preset.return_value = True
        controller = Controller(state, bus, presets, Mock(), port)
        event = Event(EventType.PRESET_SAVE_REQUESTED, {'name': 'PersonB', 'camera': 1})
        controller._on_preset_save_requested(event)
        bus.emit.assert_not_called()
        slot = presets.get_preset_for_name('PersonB')
        controller._on_preset_save_requested(event)
        assert save.call_count == 2
        assert presets.get_preset_for_name('PersonB') == slot
        assert port.save_preset.call_args_list[0] == port.save_preset.call_args_list[1]
        if retry_succeeds:
            bus.emit.assert_called_once_with(EventType.PRESET_SAVED, camera=1,
                                              name='PersonB', slot=slot)
            # Once it is durable, ordinary overwrites need no mapping save.
            controller._on_preset_save_requested(event)
            assert save.call_count == 2
        else:
            bus.emit.assert_not_called()


def test_failed_camera_retry_keeps_pending_camera_confirmed_slot():
    with patch('application.preset_service.load_chairman_presets', return_value={}), \
         patch('application.preset_service.save_chairman_presets',
               side_effect=[False, True]) as save:
        presets = PresetService()
        state = SystemState()
        state.session.active = True
        bus, port = Mock(), Mock()
        port.save_preset.side_effect = [True, False, True]
        controller = Controller(state, bus, presets, Mock(), port)
        event = Event(EventType.PRESET_SAVE_REQUESTED, {'name': 'PersonB', 'camera': 1})
        controller._on_preset_save_requested(event)
        slot = presets.get_preset_for_name('PersonB')
        controller._on_preset_save_requested(event)
        assert presets.has_preset('PersonB')
        bus.emit.assert_not_called()
        controller._on_preset_save_requested(event)
        assert save.call_count == 2
        bus.emit.assert_called_once_with(EventType.PRESET_SAVED, camera=1,
                                          name='PersonB', slot=slot)


@pytest.mark.parametrize('retry_succeeds', [False, True])
def test_renamed_pending_slot_is_persisted_before_saved_feedback(retry_succeeds):
    with patch('application.preset_service.load_chairman_presets', return_value={}), \
         patch('application.preset_service.save_chairman_presets',
               side_effect=[False, False, retry_succeeds]) as save:
        presets = PresetService()
        state = SystemState()
        state.session.active = True
        bus, port = Mock(), Mock()
        port.save_preset.return_value = True
        controller = Controller(state, bus, presets, Mock(), port)
        controller._on_preset_save_requested(Event(
            EventType.PRESET_SAVE_REQUESTED, {'name': 'PersonA', 'camera': 1},
        ))
        slot = presets.get_preset_for_name('PersonA')
        assert not presets.rename('PersonA', 'PersonB')  # disk still unavailable
        assert presets.get_preset_for_name('PersonB') == slot
        bus.emit.assert_not_called()
        controller._on_preset_save_requested(Event(
            EventType.PRESET_SAVE_REQUESTED, {'name': 'PersonB', 'camera': 1},
        ))
        assert save.call_count == 3
        assert save.call_args.args[0] == {'PersonB': slot}
        if retry_succeeds:
            bus.emit.assert_called_once_with(EventType.PRESET_SAVED, camera=1,
                                              name='PersonB', slot=slot)
        else:
            bus.emit.assert_not_called()
