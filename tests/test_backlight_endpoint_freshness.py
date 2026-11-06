"""Backlight confirmations belong only to the endpoint that sent them."""
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter


@pytest.mark.parametrize("change", ["ip", "id", "roundtrip"])
def test_retired_backlight_confirmation_does_not_repopulate_state(change):
    adapter = ViscaCameraAdapter(Mock(), {1: ("192.0.2.1", "81")})

    def confirm_old_endpoint(ip, visca_id, command):
        if change == "id":
            adapter.update_camera_visca_id(1, "83")
        else:
            adapter.update_camera_ip(1, "192.0.2.3")
            if change == "roundtrip":
                adapter.update_camera_ip(1, "192.0.2.1")
        return True

    adapter._send_confirmed = confirm_old_endpoint
    assert adapter.backlight_toggle("cam1").ok
    assert not adapter._backlight_on.get("cam1", False)
    commands = []
    adapter._send_confirmed = lambda ip, visca_id, cmd: commands.append(cmd) or True
    assert adapter.backlight_toggle("cam1").ok
    assert commands == ["01043302FF"]


def test_failed_toggle_preserves_current_backlight_state():
    adapter = ViscaCameraAdapter(Mock(), {1: ("192.0.2.1", "81")})
    adapter._backlight_on["cam1"] = True
    adapter._send_confirmed = Mock(return_value=False)
    assert not adapter.backlight_toggle("cam1").ok
    assert adapter._backlight_on["cam1"] is True
