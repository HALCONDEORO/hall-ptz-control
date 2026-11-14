# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Camera display query wiring and Qt delivery-time freshness guards."""
import weakref

from PyQt5.QtCore import pyqtSlot


def _queue_display_update(window_ref, method, *values):
    """A transport callback must not invoke a destroyed Qt receiver."""
    from PyQt5 import sip
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

    window = window_ref()
    if window is None or sip.isdeleted(window) or getattr(window, "_shutting_down", False):
        return
    try:
        QMetaObject.invokeMethod(
            window, method, Qt.QueuedConnection,
            *(Q_ARG(int, value) for value in values),
        )
    except RuntimeError:
        # Destruction can race the check above on the Qt thread. Only swallow
        # that lifetime error, not an invalid method or another programming bug.
        if not sip.isdeleted(window):
            raise

from ui.display_freshness import capture_display_generation, display_update_is_current


class CameraDisplayMixin:
    """Presentation-only bridge used by MainWindow, with no hardware I/O."""

    def _on_cam_connection_changed(self, ok: bool, ip: str) -> None:
        """Refleja el estado de conexión del worker en el LED de la cámara.

        Se cablea para CADA worker (incluidos los recreados tras un cambio de
        IP), de modo que el indicador siga al worker actual y no se quede
        pegado en el estado del worker de arranque.
        """
        try:
            cam_key = self._cameras.cam_key(ip)
        except ValueError:
            return
        ok = self._cameras.is_connected(ip)  # delivery-time transport snapshot
        (self.Cam1 if cam_key == 1 else self.Cam2).set_connected(ok)
        self._update_controls_visibility()

    @pyqtSlot()
    def _apply_focus_update(self) -> None:
        """Recheck shutdown when queued confirmed focus feedback is delivered."""
        if getattr(self, "_shutting_down", False):
            return
        self._update_focus_ui()

    def _selected_cam_key(self) -> int:
        return 1 if self.Cam1.isChecked() else 2

    def _refresh_zoom(self) -> None:
        """Refresh the zoom slider from cache or network query via CameraPort."""
        if getattr(self, "_shutting_down", False):
            return
        window_ref = weakref.ref(self)
        cam_key = self._selected_cam_key()
        generation = capture_display_generation(self._camera_port, cam_key)
        intent_generation = getattr(self, '_zoom_intent_generation', 0)
        self._camera_port.refresh_zoom_display(
            cam_key,
            lambda pct: _queue_display_update(
                window_ref, "_apply_zoom_feedback", cam_key, generation, pct, intent_generation,
            ),
        )

    @pyqtSlot(int, int, int)
    @pyqtSlot(int, int, int, int)
    def _apply_zoom_feedback(self, cam_key: int, generation: int, pct: int,
                             intent_generation: int = -1) -> None:
        """Queued zoom result: drop it if the camera was reconfigured meanwhile."""
        if getattr(self, "_shutting_down", False):
            return
        if (intent_generation != -1
                and intent_generation != getattr(self, '_zoom_intent_generation', 0)):
            return
        if not display_update_is_current(
            self._camera_port, cam_key, generation, self._selected_cam_key()
        ):
            return
        self._set_zoom_feedback(pct)

    def _on_zoom_invalidated(self, event) -> None:
        """An explicit camera action retired zoom; read without a zoom command."""
        if (getattr(self, "_shutting_down", False)
                or not getattr(self, "session_active", False)
                or event.payload.get("camera") != self._selected_cam_key()):
            return
        self._refresh_zoom()

    def _on_cam_connected(self, ok: bool, ip: str) -> None:
        if not ok or getattr(self, "_shutting_down", False):
            return
        try:
            cam_key = self._cameras.cam_key(ip)
        except ValueError:
            # A retired worker may still have a queued connection signal.
            # It must not trigger a query against an unrelated camera slot.
            return
        # A camera can reconnect after a preset or an external remote changed
        # its zoom. A pre-disconnection cache is not a new observation.
        self._camera_port.invalidate_zoom(cam_key)
        if (getattr(self, "session_active", False)
                and cam_key == self._selected_cam_key()):
            self._refresh_zoom()
        window_ref = weakref.ref(self)
        generation = capture_display_generation(self._camera_port, cam_key)
        # The query thread calls this back; hop to the Qt thread and re-check.
        self._camera_port.async_refresh_ae_mode(
            cam_key,
            lambda: _queue_display_update(
                window_ref, "_apply_exposure_update", cam_key, generation,
            ),
        )

    @pyqtSlot(int, int)
    def _apply_exposure_update(self, cam_key: int, generation: int) -> None:
        """Queued AE/exposure result: drop it if the camera was reconfigured."""
        if getattr(self, "_shutting_down", False):
            return
        if not display_update_is_current(
            self._camera_port, cam_key, generation, self._selected_cam_key()
        ):
            return
        self._update_exposure_ui()
