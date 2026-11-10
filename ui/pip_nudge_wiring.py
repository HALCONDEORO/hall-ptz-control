"""Wire manual camera activity and target-scoped PiP cancellation, without Qt."""
from core.events import EventType


def wire_pip_nudge_activity(window) -> None:
    """Register callbacks once after the PiP service has been constructed."""
    for _evt in (EventType.CAMERA_MOVE, EventType.CAMERA_ZOOM, EventType.SEAT_SELECTED):
        window._bus.subscribe(_evt, lambda _e: window._record_activity())
        window._bus.subscribe(_evt, lambda _e: window._atem_dispatcher.notify_manual_control())
    # El nudge solo se cancela ante comandos que SUSTITUYEN el paneo en curso:
    # un nuevo move (nueva velocidad de pan) o un recall de preset / sede
    # (posición absoluta).  CAMERA_ZOOM no afecta al eje pan, así que cancelar
    # dejaría el move() del nudge sin su stop_move() programado → deriva.
    for _evt in (EventType.CAMERA_MOVE, EventType.SEAT_SELECTED):
        window._bus.subscribe(
            _evt,
            lambda _e: window._pip_nudge_svc.cancel_for_camera(
                f"cam{_e.payload.get('camera', window._state.active_camera)}"
            ),
        )
