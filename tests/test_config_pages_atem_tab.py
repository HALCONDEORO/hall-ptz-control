#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# tests/test_config_pages_atem_tab.py — ui/config_pages/atem_tab.py had no coverage
#
# Real tab widgets: manual IP editing and monitor status remain available;
# unsupported discovery/TCP probes must never claim a switcher was ruled out.

from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")

from tests.config_pages_harness import (          # noqa: E402
    button_named, buttons, has_text, label_texts, make_harness, panel_layout,
)


@pytest.fixture(autouse=True)
def configured_atem(monkeypatch):
    import config
    monkeypatch.setattr(config.ATEM, "ip", "172.16.1.50", raising=False)



def build(monkeypatch, *, is_on=False, sim_active=False, visible=True,
          state=None, last_error="", inline=True):
    dialog, mw, layout = make_harness(visible=visible)
    mw._atem_monitor.state = state
    mw._atem_monitor.last_error = last_error
    import ui.config_pages.atem_tab as tab
    tab.build_atem_tab(dialog, layout, mw, is_on, sim_active, panel_layout)
    return dialog, mw, layout


def pill_text(layout) -> str:
    """The connection-status pill's text.

    Matched exactly, not by substring: "Disconnected" contains "connected", so a
    loose check would report a broken switcher as a healthy one.
    """
    for text in label_texts(layout):
        if text.strip().startswith("●"):
            return text.strip()
    raise AssertionError(f"no status pill; got {label_texts(layout)}")


def error_label(layout):
    """The "Last error:" line — hidden rather than emptied when it goes stale."""
    from PyQt5.QtWidgets import QLabel

    for label in layout.parentWidget().findChildren(QLabel):
        if label.text().startswith("Last error"):
            return label
    raise AssertionError("no 'Last error' label found")


class TestSwitcherCard:
    def test_the_configured_ip_is_shown(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        assert "172.16.1.50" in label_texts(layout)

    def test_discovery_is_explicitly_unavailable(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        assert not button_named(layout, "Discover switchers").isEnabled()

    def test_unverified_tcp_probe_is_disabled(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        assert not button_named(layout, "Scan").isEnabled()


class TestStatusPill:
    def test_connected_state_is_shown(self, monkeypatch):
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch, state=ATEMState.CONNECTED)
        assert pill_text(layout) == "● Connected"

    def test_disconnected_state_is_shown(self, monkeypatch):
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch, state=ATEMState.DISCONNECTED)
        assert pill_text(layout) == "● Disconnected"

    def test_a_missing_dependency_is_named(self, monkeypatch):
        """python-atem absent is a different fix from a cable problem."""
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch, state=ATEMState.DEPENDENCY_MISSING)
        assert pill_text(layout) == "● Library missing"

    def test_an_unknown_state_does_not_claim_a_connection(self, monkeypatch):
        """No monitor yet — the pill must not read "Connected"."""
        dialog, mw, layout = build(monkeypatch, state=None)
        assert pill_text(layout) == "● Unknown"

    def test_every_state_has_a_label(self, monkeypatch):
        from domain.atem_state import ATEMState
        for state in ATEMState:
            dialog, mw, layout = build(monkeypatch, state=state)
            assert pill_text(layout) != "● Unknown", state

    def test_the_last_error_is_shown_when_there_is_one(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch, last_error="connection refused")
        assert has_text(layout, "connection refused")

    def test_no_error_line_when_healthy(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch, last_error="")
        assert not has_text(layout, "Last error")


class TestUnsupportedProbes:
    @pytest.mark.parametrize('is_on', [True, False])
    @pytest.mark.parametrize('sim_active', [True, False])
    def test_no_probe_can_run_or_repoint_switcher(self, monkeypatch, is_on, sim_active):
        dialog, mw, layout = build(monkeypatch, is_on=is_on, sim_active=sim_active)
        for name in ('Discover switchers', 'Scan'):
            btn = button_named(layout, name)
            assert not btn.isEnabled()
            btn.click()
        assert mw.restarts == 0
        assert mw._camera_config.atem_ips == []
        assert has_text(layout, 'enter the switcher IP manually')
        assert 'Reconnect ATEM' in button_named(layout, 'Scan').toolTip()

    def test_manual_ip_edit_is_still_present(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        assert any(b.isEnabled() and not b.text() and not b.icon().isNull() for b in buttons(layout))


class TestReconnect:
    def test_it_restarts_the_monitor(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        button_named(layout, "Reconnect ATEM").click()
        assert mw.restarts == 1

    def test_the_button_is_held_while_reconnecting(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        btn = button_named(layout, "Reconnect ATEM")
        btn.click()
        assert not btn.isEnabled()
        assert btn.text() == "Reconnecting…"

    def test_the_stale_error_is_cleared(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch, last_error="connection refused")
        button_named(layout, "Reconnect ATEM").click()
        assert error_label(layout).isHidden()


class TestMonitorUpdates:
    def test_the_pill_follows_the_monitor(self, monkeypatch):
        """The monitor reaches CONNECTED on its own, after the tab was built."""
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch, state=ATEMState.DISCONNECTED)
        mw.atem_state_changed.emit(ATEMState.CONNECTED)
        assert pill_text(layout) == "● Connected"

    def test_a_new_error_is_surfaced(self, monkeypatch):
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch)
        mw._atem_monitor.last_error = "no route to host"
        mw.atem_state_changed.emit(ATEMState.ERROR)
        assert has_text(layout, "no route to host")

    def test_the_reconnect_button_is_released(self, monkeypatch):
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch)
        btn = button_named(layout, "Reconnect ATEM")
        btn.click()
        mw.atem_state_changed.emit(ATEMState.CONNECTED)
        assert btn.isEnabled()
        assert btn.text() == "Reconnect ATEM"

    def test_it_stops_listening_once_the_dialog_is_gone(self, monkeypatch):
        """A slot still bound to a deleted widget tree crashes the app the next
        time the monitor changes state."""
        from domain.atem_state import ATEMState
        dialog, mw, layout = build(monkeypatch, state=ATEMState.DISCONNECTED)
        dialog.destroyed.emit()          # what Qt emits when the dialog dies
        mw.atem_state_changed.emit(ATEMState.CONNECTED)
        assert pill_text(layout) == "● Disconnected"


class TestControlPanelButton:
    def test_absent_when_there_is_no_panel(self, monkeypatch):
        dialog, mw, layout = build(monkeypatch)
        assert not any("Control Panel" in b.text() for b in buttons(layout))

    def test_opens_the_panel_and_closes_the_settings_sheet(self, monkeypatch):
        dialog, mw, layout = make_harness()
        mw._atem_panel = object()
        import ui.config_pages.atem_tab as tab
        tab.build_atem_tab(dialog, layout, mw, False, False, panel_layout)
        button_named(layout, "Control Panel").click()
        assert mw.panel_toggles == 1
        assert dialog.accepted_count == 1
