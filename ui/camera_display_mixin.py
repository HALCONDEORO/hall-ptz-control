# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Camera display query wiring and Qt delivery-time freshness guards."""
from PyQt5.QtCore import pyqtSlot

from ui.display_freshness import capture_display_generation, display_update_is_current


class CameraDisplayMixin:
    """Presentation-only bridge used by MainWindow, with no hardware I/O."""

    def _selected_cam_key(self) -> int:
        return 1 if self.Cam1.isChecked() else 2

    def _refresh_zoom(self) -> None:
        """Refresh the zoom slider from cache or network query via CameraPort."""
        from PyQt5.QtCore import QMetaObject, Qt, Q_ARG  # noqa: PLC0415
        cam_key = self._selected_cam_key()
        generation = capture_display_generation(self._camera_port, cam_key)
        self._camera_port.refresh_zoom_display(
            cam_key,
            lambda pct: QMetaObject.invokeMethod(
                self, "_apply_zoom_feedback", Qt.QueuedConnection,
                Q_ARG(int, cam_key), Q_ARG(int, generation), Q_ARG(int, pct),
            ),
        )

    @pyqtSlot(int, int, int)
    def _apply_zoom_feedback(self, cam_key: int, generation: int, pct: int) -> None:
        """Queued zoom result: drop it if the camera was reconfigured meanwhile."""
        if not display_update_is_current(
            self._camera_port, cam_key, generation, self._selected_cam_key()
        ):
            return
        self._set_zoom_feedback(pct)

    def _on_cam_connected(self, ok: bool, ip: str) -> None:
        if not ok:
            return
        try:
            cam_key = self._cameras.cam_key(ip)
        except ValueError:
            # A retired worker may still have a queued connection signal.
            # It must not trigger a query against an unrelated camera slot.
            return
        from PyQt5.QtCore import QMetaObject, Qt, Q_ARG  # noqa: PLC0415
        generation = capture_display_generation(self._camera_port, cam_key)
        # The query thread calls this back; hop to the Qt thread and re-check.
        self._camera_port.async_refresh_ae_mode(
            cam_key,
            lambda: QMetaObject.invokeMethod(
                self, "_apply_exposure_update", Qt.QueuedConnection,
                Q_ARG(int, cam_key), Q_ARG(int, generation),
            ),
        )

    @pyqtSlot(int, int)
    def _apply_exposure_update(self, cam_key: int, generation: int) -> None:
        """Queued AE/exposure result: drop it if the camera was reconfigured."""
        if not display_update_is_current(
            self._camera_port, cam_key, generation, self._selected_cam_key()
        ):
            return
        self._update_exposure_ui()
