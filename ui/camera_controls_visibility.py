"""Hide PTZ controls only after a sustained transport loss, never on a blip."""
from PyQt5.QtCore import QTimer

DISCONNECT_HIDE_DELAY_MS = 1800


class CameraControlsVisibility:
    def __init__(self, window):
        self.window = window
        self.visible = False
        self.camera = None
        self.timer = QTimer(window)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._hide_if_still_disconnected)

    def _snapshot(self):
        key = 1 if self.window.Cam1.isChecked() else 2
        camera = self.window.Cam1 if key == 1 else self.window.Cam2
        return key, bool(camera._connected)

    def _show(self, visible):
        self.visible = visible
        self.window._right_panel.show_camera_controls(visible)

    def update(self):
        key, connected = self._snapshot()
        changed_camera = self.camera != key
        self.camera = key
        if not self.window.session_active or getattr(self.window, '_shutting_down', False):
            self.timer.stop()
            self._show(False)
        elif connected:
            self.timer.stop()
            self._show(True)
        elif changed_camera or not self.visible:
            # No grace on initial startup or switching to an offline camera.
            self.timer.stop()
            self._show(False)
        elif not self.timer.isActive():
            self.timer.start(DISCONNECT_HIDE_DELAY_MS)

    def _hide_if_still_disconnected(self):
        key, connected = self._snapshot()
        if key != self.camera or connected or not self.window.session_active:
            self.update()
        else:
            self._show(False)


def update_camera_controls_visibility(window):
    controller = window.__dict__.get('_camera_controls_visibility')
    if controller is None:
        controller = CameraControlsVisibility(window)
        window._camera_controls_visibility = controller
    controller.update()
