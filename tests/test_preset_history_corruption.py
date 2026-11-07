"""Damaged history must not stop the test settings tab from opening."""
import json

import pytest

from application.preset_test_history_service import PresetTestHistoryService


@pytest.mark.parametrize('bad', [None, [], 'damaged', 9, True])
def test_non_object_latest_record_yields_no_run(tmp_path, bad):
    path = tmp_path / 'history.json'
    path.write_text(json.dumps([{'total': 8, 'ok': 8}, bad]))
    service = PresetTestHistoryService(path)
    assert service.last_entry() is None
    assert service.summary_line() == 'No test runs yet'


@pytest.mark.parametrize('bad', [None, 9, [], {}])
def test_non_string_timestamp_does_not_break_summary(tmp_path, bad):
    path = tmp_path / 'history.json'
    path.write_text(json.dumps([{'timestamp': bad, 'total': 8, 'ok': 7}]))
    line = PresetTestHistoryService(path).summary_line()
    assert '7/8 OK' in line
