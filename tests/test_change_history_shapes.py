"""Valid JSON of the wrong shape must not hide valid change events."""
import json

import pytest

from application.change_history_service import ChangeHistoryService
from domain.change_event import ChangeEvent


@pytest.mark.parametrize('bad', [None, [], 'damaged', 7, True])
def test_bad_shape_line_is_skipped_but_good_lines_survive(tmp_path, bad):
    path = tmp_path / 'changes.json'
    first = ChangeEvent('config', 'changed', 'camera:1')
    last = ChangeEvent('config', 'changed', 'camera:2')
    path.write_text('\n'.join([json.dumps(first.to_dict()), json.dumps(bad),
                               json.dumps(last.to_dict())]) + '\n')
    events = ChangeHistoryService(path).read_recent(10)
    assert [e.target for e in events] == ['camera:1', 'camera:2']
    assert path.read_text().count('\n') == 3
