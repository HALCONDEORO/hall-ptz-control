"""Canonical roles, legacy reads and safety-context regression matrix."""
import json

import pytest

from application.access_mode_service import AccessModeService
from application.call_set_command_policy import CallSetCommandPolicy
from domain.atem_policy import can_live_switch
from domain.call_set_policy import CallSetAction, InputType, OperatingMode

LEGACY = [(value, OperatingMode.USER) for value in
          ('user', 'camera_operator', 'basic_operator', 'operator')] + [
              (value, OperatingMode.ADMIN) for value in
              ('admin', 'technician', 'system_admin', 'admin_installer')]
CONTEXTS = [OperatingMode.SUPPORT, OperatingMode.DEMO, OperatingMode.NAME_EDIT,
            OperatingMode.LAYOUT_EDIT, OperatingMode.PRESET_TEST, OperatingMode.NAMES]


@pytest.mark.parametrize('raw,expected', LEGACY)
@pytest.mark.parametrize('source', ['file', 'KHPTZ_ACCESS_ROLE', 'KHPTZ_ACCESS_MODE'])
def test_legacy_read_and_canonical_write(tmp_path, monkeypatch, raw, expected, source):
    monkeypatch.delenv('KHPTZ_ACCESS_ROLE', raising=False)
    monkeypatch.delenv('KHPTZ_ACCESS_MODE', raising=False)
    path = tmp_path / 'role.json'
    if source == 'file':
        path.write_text(json.dumps({'access_mode': raw}))
    else:
        monkeypatch.setenv(source, raw)
    service = AccessModeService(path=path)
    assert service.mode is expected
    service.set_mode(service.mode)
    assert json.loads(path.read_text()) == {'access_mode': expected.value}
    assert expected.value in {'user', 'admin'}


@pytest.mark.parametrize('raw,expected', LEGACY)
def test_role_policy_after_migration(raw, expected):
    mode = OperatingMode(raw)
    assert mode is expected
    policy = CallSetCommandPolicy()
    for gesture in (InputType.RIGHT_CLICK, InputType.LONG_PRESS):
        decision = policy.decide(mode, gesture, True, True)
        assert decision.allowed and decision.requires_confirmation
        assert decision.action is CallSetAction.SET
    assert policy.decide(mode, InputType.TAP, True, True).allowed
    assert can_live_switch(mode) is (expected is OperatingMode.ADMIN)


@pytest.mark.parametrize('context', CONTEXTS)
def test_context_never_becomes_access_role_or_live_permission(tmp_path, context):
    path = tmp_path / 'role.json'
    path.write_text(json.dumps({'access_mode': context.value}))
    service = AccessModeService(path=path)
    assert service.mode is OperatingMode.USER
    with pytest.raises(ValueError):
        service.set_mode(context)
    assert not can_live_switch(context)
    for gesture in InputType:
        assert not CallSetCommandPolicy().decide(context, gesture, True, True).allowed


def test_role_env_has_priority_over_legacy_env_and_file(tmp_path, monkeypatch):
    path = tmp_path / 'role.json'
    path.write_text('{"access_mode":"admin"}')
    monkeypatch.setenv('KHPTZ_ACCESS_ROLE', 'user')
    monkeypatch.setenv('KHPTZ_ACCESS_MODE', 'technician')
    assert AccessModeService(path=path).mode is OperatingMode.USER
