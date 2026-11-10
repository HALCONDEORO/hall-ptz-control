#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# domain/atem_policy.py — Single source of truth for ATEM permission rules
#
# Pure domain rules: no PyQt, no I/O, no sockets. Both the application service
# (AtemCommandService) and the admin UI (AtemAdminPanel) must decide "who may
# switch live" from this one predicate, so the rule can never drift between the
# guard that blocks the command and the button that enables it.

from __future__ import annotations

from domain.call_set_policy import OperatingMode

# Only the administrator access role can switch live.
LIVE_SWITCH_ROLES = frozenset({OperatingMode.ADMIN})


def can_live_switch(role: OperatingMode) -> bool:
    """True when *role* may perform live ATEM switching (CUT/AUTO/set preview control).

    This is the one rule both the command guard and the UI enabling logic
    consult. Setting preview alone does not cause an on-air transition and is
    intentionally not gated here — only the live-switch actions are.
    """
    return role in LIVE_SWITCH_ROLES
