# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Explicit service results, not truthy test mocks, decide edit completion."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from ui.config_edit_dialogs import _CamEditDialog, _ATEMEditDialog


@pytest.mark.parametrize('kind', ['ip', 'visca_id', 'atem'])
@pytest.mark.parametrize('code,accepted,warned', [('OK',True,False),
    ('PARTIAL_OK',True,True), ('INVALID_INPUT',False,False)])
def test_applied_partial_change_warns_then_closes_but_rejection_stays_open(monkeypatch, kind, code, accepted, warned):
    warning = Mock()
    monkeypatch.setattr('ui.config_edit_dialogs.QMessageBox.warning', warning)
    result = SimpleNamespace(code=code, message='Not saved')
    service = Mock()
    service.set_camera_ip.return_value = result
    service.set_camera_visca_id.return_value = result
    service.set_atem_ip.return_value = result
    dialog = Mock()
    dialog._mw = SimpleNamespace(_camera_config=service)
    dialog._input.text.return_value = '192.0.2.21' if kind != 'visca_id' else '81'
    dialog._config_type = kind
    dialog._cam_num = 1
    dialog._validate.return_value = True
    if kind == 'atem':
        _ATEMEditDialog._apply(dialog)
    else:
        _CamEditDialog._apply(dialog)
    assert dialog.accept.called is accepted
    assert warning.called is warned
    if warned:
        assert 'session only' in warning.call_args.args[2]
