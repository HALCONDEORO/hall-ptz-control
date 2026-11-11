# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# ui/config_pages/atem_tab.py — ConfigDialog "ATEM" tab (#894 phase 3)
#
# Manual ATEM IP config + monitor status/reconnect + the automation card.
# Discovery and Scan remain visible but disabled until verified support exists.
# Extracted from ConfigDialog._build_ui; self -> dialog; is_on, sim_active and
# _panel_layout are params. ATEM IP writes route through CameraConfigService.

from __future__ import annotations


from config import ATEM
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.config_edit_dialogs import _ATEMEditDialog
from ui.config_pages.sections import build_atem_automation_section
from ui.styles import (
    ERROR as _C_ERROR,
    ERROR_BD as _C_ERROR_BD,
    ERROR_BG as _C_ERROR_BG,
    MUTED as _C_MUTED,
    SECONDARY as _C_SECONDARY,
    SUCCESS as _C_SUCCESS,
    SUCCESS_BD as _C_SUCCESS_BD,
    SUCCESS_BG as _C_SUCCESS_BG,
    WARNING as _C_WARNING,
    WARNING_BD as _C_WARNING_BD,
    WARNING_BG as _C_WARNING_BG,
)


def build_atem_tab(dialog, atem_layout, mw, is_on, sim_active, panel_layout):
    """Populate the ATEM tab: manual IP, status/reconnect and automation."""
    # ── ATEM: Switcher + Automation stacked in one column ──────────────
    # Single column (not the design's 2-up grid): on this taller dialog body
    # two short side-by-side cards left a huge empty band underneath. Stacking
    # fills the space and keeps each card full-width like the other tabs.
    _atem_col1_l = atem_layout
    _atem_col2_l = atem_layout

    # ── Sección: ATEM Switcher ────────────────────────────────────────
    layout = panel_layout(_atem_col1_l, 'ATEM Switcher')

    atem_row_w = dialog._field_row('IP', ATEM.ip, on_edit=None)
    _atem_val_lbl = atem_row_w.findChild(QLabel, 'field_value')
    btn_atem_ip_w = atem_row_w.findChild(QPushButton)
    if btn_atem_ip_w:
        def _edit_atem_ip(_, lbl=_atem_val_lbl):
            _ATEMEditDialog(dialog, mw).exec_()
            import config as _cfg
            if lbl:
                lbl.setText(_cfg.ATEM.ip)
        btn_atem_ip_w.clicked.connect(_edit_atem_ip)
        dialog._lock_if_live(btn_atem_ip_w, is_on,
                           'Stop the session before changing the ATEM IP',
                           dim_target=atem_row_w)
    layout.addWidget(atem_row_w)

    # Field-row bottom separator
    _atem_sep = QFrame()
    _atem_sep.setFrameShape(QFrame.HLine)
    _atem_sep.setFixedHeight(1)
    _atem_sep.setStyleSheet("background: #F0F1EE; border: none;")
    layout.addWidget(_atem_sep)

    # No verified automatic-discovery protocol is available. TCP 9910 is not
    # evidence for or against a UDP ATEM switcher; never show "none found".
    atem_disc_desc = QLabel(
        "Automatic ATEM discovery unavailable; enter the switcher IP manually."
    )
    atem_disc_desc.setWordWrap(True)
    atem_disc_desc.setStyleSheet(
        f"font: 400 12px 'Inter Tight', 'Segoe UI'; color: {_C_MUTED};"
    )
    layout.addWidget(atem_disc_desc)
    btn_atem_discover = dialog._btn('Discover switchers', variant='primary', icon='search')
    btn_atem_discover.setEnabled(False)
    btn_atem_discover.setToolTip('Discovery unsupported: use the IP edit above')
    layout.addWidget(btn_atem_discover, 0, Qt.AlignRight)

    # Separator before the connection-status section
    _atem_sep_disc = QFrame()
    _atem_sep_disc.setFrameShape(QFrame.HLine)
    _atem_sep_disc.setFixedHeight(1)
    _atem_sep_disc.setStyleSheet("background: #F0F1EE; border: none;")
    layout.addWidget(_atem_sep_disc)

    # ── Estado ATEM actual ────────────────────────────────────────────────
    from domain.atem_state import ATEMState as _ATEMState

    _STATE_STYLE = {
        _ATEMState.CONNECTED:          ('ok',      '● Connected'),
        _ATEMState.CONNECTING:         ('warn',    '● Connecting…'),
        _ATEMState.RECONNECTING:       ('warn',    '● Reconnecting…'),
        _ATEMState.DISCONNECTED:       ('error',   '● Disconnected'),
        _ATEMState.ERROR:              ('error',   '● Error'),
        _ATEMState.NOT_CONFIGURED:     ('neutral', '● Not configured'),
        _ATEMState.DEPENDENCY_MISSING: ('neutral', '● Library missing'),
    }

    _mon = getattr(mw, '_atem_monitor', None)
    _cur_state = getattr(_mon, 'state', None)

    def _atem_status_values(state):
        return _STATE_STYLE.get(state, ('neutral', '● Unknown'))

    _atem_pill_state, _atem_pill_text = _atem_status_values(_cur_state)
    atem_status_pill = dialog._status_pill(_atem_pill_text, state=_atem_pill_state)
    layout.addWidget(atem_status_pill)

    # ── Last ATEM error ───────────────────────────────────────────────────
    _init_error = getattr(_mon, 'last_error', '')
    last_error_lbl = QLabel(f'Last error: {_init_error}' if _init_error else '')
    last_error_lbl.setStyleSheet(
        f"font: 11px 'Inter Tight', 'Segoe UI'; color: {_C_ERROR};"
    )
    last_error_lbl.setWordWrap(True)
    last_error_lbl.setVisible(bool(_init_error))
    layout.addWidget(last_error_lbl)

    # ── Botón Reconnect ATEM ──────────────────────────────────────────────
    btn_reconnect = dialog._btn('Reconnect ATEM', variant='ghost', icon='refresh')

    def _set_atem_status(state):
        kind, text = _atem_status_values(state)
        _pill_map = {
            'ok':      (_C_SUCCESS_BG,  _C_SUCCESS_BD,  _C_SUCCESS,   'green'),
            'warn':    (_C_WARNING_BG,  _C_WARNING_BD,  _C_WARNING,   'amber'),
            'error':   (_C_ERROR_BG,    _C_ERROR_BD,    _C_ERROR,     'red'),
            'neutral': ('#F4F5F3',      '#E6E8E5',      _C_SECONDARY, 'off'),
        }
        bg, bd, fg, led_state = _pill_map.get(kind, _pill_map['neutral'])
        # _status_pill devuelve un QWidget contenedor — actualizar hijos.
        atem_status_pill.setStyleSheet(
            f"background: {bg}; border: 1px solid {bd}; border-radius: 8px;"
        )
        from PyQt5.QtWidgets import QLabel as _QLabel
        led = atem_status_pill.findChild(_QLabel, 'led_dot')
        if led:
            dialog._set_led(led, led_state)
        text_labels = [lb for lb in atem_status_pill.findChildren(_QLabel)
                       if lb.objectName() != 'led_dot']
        if text_labels:
            text_labels[0].setText(text)
            text_labels[0].setStyleSheet(
                f"font: 600 13px 'Inter Tight', 'Segoe UI';"
                f" color: {fg}; background: transparent;"
            )

    def _on_reconnect():
        btn_reconnect.setEnabled(False)
        btn_reconnect.setText('Reconnecting…')
        last_error_lbl.setVisible(False)
        mw._do_restart_atem_monitor()
        _set_atem_status(_ATEMState.CONNECTING)

    def _on_dialog_atem_state(state):
        _set_atem_status(state)
        btn_reconnect.setEnabled(True)
        btn_reconnect.setText('Reconnect ATEM')
        err = getattr(getattr(mw, '_atem_monitor', None), 'last_error', '')
        last_error_lbl.setText(f'Last error: {err}' if err else '')
        last_error_lbl.setVisible(bool(err))

    btn_reconnect.clicked.connect(_on_reconnect)
    mw.atem_state_changed.connect(_on_dialog_atem_state)
    def _on_dialog_destroyed(_=None) -> None:
        try:
            dialog._disconnect_signal(mw.atem_state_changed, _on_dialog_atem_state)
        except RuntimeError:
            pass  # mw already deleted during app shutdown

    dialog.destroyed.connect(_on_dialog_destroyed)

    # No TCP probe: only the real monitor can confirm an ATEM connection.
    btn_scan_atem = dialog._btn('Scan', variant='ghost', icon='search')
    btn_scan_atem.setEnabled(False)
    btn_scan_atem.setToolTip(
        'TCP scan unavailable for ATEM (UDP); use Reconnect ATEM and monitor status'
    )

    _atem_btn_row = QHBoxLayout()
    _atem_btn_row.addStretch()
    _atem_btn_row.addWidget(btn_scan_atem)
    _atem_btn_row.addWidget(btn_reconnect)
    layout.addLayout(_atem_btn_row)

    # ── Botón abrir panel ATEM ────────────────────────────────────────────
    _atem_panel = getattr(mw, '_atem_panel', None)
    if _atem_panel is not None:
        _sep2 = QFrame()
        _sep2.setFrameShape(QFrame.HLine)
        _sep2.setFixedHeight(1)
        _sep2.setStyleSheet("background: #F0F1EE; border: none;")
        layout.addWidget(_sep2)

        btn_open_panel = dialog._btn('ATEM Control Panel  →', variant='primary', icon='monitor')
        btn_open_panel.setToolTip('Open the ATEM switcher control buttons')

        def _on_open_atem_panel():
            mw._toggle_atem_panel()
            dialog.accept()

        btn_open_panel.clicked.connect(_on_open_atem_panel)
        layout.addWidget(btn_open_panel, 0, Qt.AlignRight)
        from ui.atem_visibility import bind_operational_visibility
        bind_operational_visibility(mw, btn_open_panel)
        bind_operational_visibility(mw, _sep2)

    # ── Automatización ATEM ───────────────────────────────────────────────
    automation_widget = QWidget()
    automation_layout = QVBoxLayout(automation_widget)
    automation_layout.setContentsMargins(0, 0, 0, 0)
    _atem_col2_l.addWidget(automation_widget)
    layout = panel_layout(automation_layout, 'ATEM Automation')
    build_atem_automation_section(dialog, layout, mw)
    from ui.atem_visibility import bind_operational_visibility
    bind_operational_visibility(mw, automation_widget)

    atem_layout.addStretch()
