# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""State policy for the main-window ATEM button and its status dot.

Extracted from MainWindow (god-object ratchet) so the demo/sim branch can
grow honest behaviour without growing main_window.py.
"""

import logging


logger = logging.getLogger(__name__)

_DOT_GREEN = "background: #2e7d32; border-radius: 6px;"
_DOT_RED = "background: #c62828; border-radius: 6px;"


def apply_atem_button_state(btn, dot, panel, state, fake_atem, *, operative=False) -> None:
    """Never leave an unusable ATEM surface on screen (live hardware).

    Demo/sim (fake_atem present) keeps the button reachable even when the
    virtual switcher is disconnected: the demo panel owns the Reconnect
    control, so hiding the button would lock the operator out (#921).
    """
    if fake_atem is not None:
        try:
            connected = bool(fake_atem.get_status().connected)
        except Exception:
            connected = False
        visible = panel is not None
        btn.setVisible(visible)
        dot.setVisible(visible)
        btn.setEnabled(visible)
        if visible:
            dot.setStyleSheet(_DOT_GREEN if connected else _DOT_RED)
            btn.setToolTip(
                "ATEM switcher panel" if connected
                else "ATEM virtual desconectado — Reconnect en el panel")
        return
    visible = bool(panel is not None and operative)
    btn.setVisible(visible)
    dot.setVisible(visible)
    btn.setEnabled(visible)
    if visible:
        dot.setStyleSheet(_DOT_GREEN)
        btn.setToolTip("ATEM switcher panel")
    else:
        btn.setChecked(False)
        if panel is not None:
            panel.hide()
