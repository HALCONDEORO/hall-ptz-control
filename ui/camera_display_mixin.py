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

    def _selected_cam_key(self) -> int:
        return 1 if self.Cam1.isChecked() else 2

    def _refresh_zoom(self) -> None:
        """Refresh the zoom slider from cache or network query via CameraPort."""
        if getattr(self, "_shutting_down", False):
            return
        window_ref = weakref.ref(self)
        cam_key = self._selected_cam_key()
        generation = capture_display_generation(self._camera_port, cam_key)
        self._camera_port.refresh_zoom_display(
            cam_key,
            lambda pct: _queue_display_update(
                window_ref, "_apply_zoom_feedback", cam_key, generation, pct,
            ),
        )

    @pyqtSlot(int, int, int)
    def _apply_zoom_feedback(self, cam_key: int, generation: int, pct: int) -> None:
        """Queued zoom result: drop it if the camera was reconfigured meanwhile."""
        if getattr(self, "_shutting_down", False):
            return
        if not display_update_is_current(
            self._camera_port, cam_key, generation, self._selected_cam_key()
        ):
            return
        self._set_zoom_feedback(pct)

    def _on_cam_connected(self, ok: bool, ip: str) -> None:
        if not ok or getattr(self, "_shutting_down", False):
            return
        try:
            cam_key = self._cameras.cam_key(ip)
        except ValueError:
            # A retired worker may still have a queued connection signal.
            # It must not trigger a query against an unrelated camera slot.
            return
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
