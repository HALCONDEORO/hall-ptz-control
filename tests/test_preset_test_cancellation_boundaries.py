"""Cancellation seen before dispatch must not issue a new movement command."""
import threading
from unittest.mock import Mock, patch

import pytest

from application.preset_test_models import PresetTestItem, STATUS_CANCELLED
from application.preset_test_runner import PresetTestRunner


@pytest.mark.parametrize('boundary', ['started', 'highlight', 'resolve'])
def test_cancel_before_send_prevents_movement(boundary):
    send = Mock(return_value=True)
    item = PresetTestItem(item_id='seat_004', label='4', camera_role='comments',
                          camera_index=2, preset=4)
    resolved = threading.Event()
    resume = threading.Event()

    def resolve(_):
        if boundary == 'resolve':
            resolved.set()
            assert resume.wait(5), 'test did not release routing'
        return '192.0.2.1', '81'

    runner = PresetTestRunner([item], send, resolve, delay_seconds=0)
    if boundary == 'started':
        runner.on_item_started = lambda *args: runner.cancel()
    if boundary == 'highlight':
        runner.on_highlight = lambda *args: runner.cancel()
    finished = Mock()
    cancelled = Mock()
    runner.on_finished = finished
    runner.on_cancelled = cancelled
    with patch('config.PRESET_MAP', {4: '0x04'}):
        runner.start()
        try:
            if boundary == 'resolve':
                assert resolved.wait(5), 'routing never started'
                runner.cancel()
        finally:
            resume.set()
            runner._thread.join(5)
    assert not runner.is_running
    send.assert_not_called()
    finished.assert_not_called()
    cancelled.assert_called_once()
    summary = cancelled.call_args.args[0]
    assert summary.cancelled
    assert summary.ok == summary.warning == summary.error == summary.skipped == 0
    assert summary.results[0].status == STATUS_CANCELLED
