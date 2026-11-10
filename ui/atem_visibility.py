"""Live visibility bindings for ATEM operations and status."""

def bind_operational_visibility(window, widget):
    """Keep a Settings operation/status hidden as the live gate changes."""
    from PyQt5 import sip
    def refresh(_state=None):
        if not sip.isdeleted(widget):
            predicate = getattr(window, 'atem_operational', None)
            widget.setVisible(bool(predicate()) if callable(predicate) else False)
    refresh()
    signal = getattr(window, 'atem_state_changed', None)
    if signal is None or not callable(getattr(signal, 'connect', None)):
        return
    signal.connect(refresh)
    def cleanup(*_):
        try:
            signal.disconnect(refresh)
        except (TypeError, RuntimeError):
            pass
    widget.destroyed.connect(cleanup)
