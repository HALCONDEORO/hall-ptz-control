"""Live visibility bindings for ATEM operations and status."""

def bind_operational_visibility(window, widget):
    """Keep a Settings operation/status hidden as the live gate changes."""
    from PyQt5 import sip
    def refresh(_state=None):
        if not sip.isdeleted(widget):
            widget.setVisible(window.atem_operational())
    refresh()
    window.atem_state_changed.connect(refresh)
    def cleanup(*_):
        try:
            window.atem_state_changed.disconnect(refresh)
        except (TypeError, RuntimeError):
            pass
    widget.destroyed.connect(cleanup)
