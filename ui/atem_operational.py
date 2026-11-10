"""A live monitor must prove it can read program state before exposing controls."""
from PyQt5.QtCore import pyqtSlot

from domain.atem_state import ATEMState


def atem_operational(window):
    monitor = getattr(window, '_atem_monitor', None)
    return bool(
        window._atem_is_configured()
        and getattr(window, '_atem_state', None) == ATEMState.CONNECTED
        and monitor is not None
        and getattr(monitor, 'state', None) == ATEMState.CONNECTED
        and getattr(window, '_atem_verified_monitor', None) is monitor
    )


def accept_program_verification(window, input_id):
    monitor = getattr(window, '_atem_monitor', None)
    if (monitor is None or window.sender() is not monitor
            or monitor.state != ATEMState.CONNECTED
            or getattr(window, '_atem_state', None) != ATEMState.CONNECTED
            or not isinstance(input_id, int) or isinstance(input_id, bool)
            or input_id < 0):
        return
    window._atem_verified_monitor = monitor
    window.atem_state_changed.emit(window._atem_state)
    window._update_atem_button(window._atem_state)
    window._right_panel.set_atem_program(input_id)


class AtemOperationalMixin:
    """Qt receiver methods, separate from the main-window layout controller."""

    def atem_operational(self) -> bool:
        return atem_operational(self)

    @pyqtSlot(int)
    def _on_atem_program_verified(self, input_id: int) -> None:
        accept_program_verification(self, input_id)
