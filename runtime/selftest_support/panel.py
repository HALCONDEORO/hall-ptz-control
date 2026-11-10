"""Real Qt seat clicks and the production PTZ panel, without site configuration."""
import time
from types import SimpleNamespace


def run_panel_check():
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QWidget
    from ui.right_panel import RightPanel
    from ui.widgets import GoButton
    from ui.camera_controls_visibility import update_camera_controls_visibility
    from application.app_controller import ApplicationController
    from application.call_set_command_policy import CallSetCommandPolicy
    from domain.call_set_policy import InputType, OperatingMode
    from adapters.fake_camera_port import FakeCameraPort
    from core.events import EventType

    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.resize(1920, 1080)
    window.session_active = True
    window._shutting_down = False
    window._session = SimpleNamespace(_session_generation=1)
    window._refresh_zoom = lambda: None
    window._record_activity = lambda: None
    port = FakeCameraPort()
    window._camera_port = port

    class Bus:
        def emit(self, event, **payload):
            if event == EventType.SEAT_SELECTED:
                port.recall_preset('cam1', payload['preset'])
    window._bus = Bus()
    controller = ApplicationController(None, CallSetCommandPolicy(), window._bus)
    for callback in ('_update_backlight_ui', '_update_focus_ui', '_update_exposure_ui',
                     '_update_active_camera', '_open_config_dialog', '_exit_admin_mode',
                     '_enter_admin_mode_inline'):
        setattr(window, callback, lambda: None)
    window._update_controls_visibility = lambda: update_camera_controls_visibility(window)
    from application.access_mode_service import AccessModeService
    window._access_mode_svc = AccessModeService()
    panel = RightPanel(window)
    panel.connect_joystick({}, lambda: None)
    window.Cam1._connected = True
    window.Cam2._connected = True
    window._right_panel = panel
    window.show()
    panel._container.show()
    update_camera_controls_visibility(window)
    app.processEvents()

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    def pump(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)

    try:
        check(panel._controls_widget.isVisible(), 'PTZ controls hidden at healthy start')
        for index, number in enumerate((90, 102, 117, 87, 71)):
            button = GoButton(number, window)
            button.move(80 + index * 90, 80)
            button.init_preset_actions(number, lambda preset: controller.recall_seat(
                seat_id=preset, preset=preset, input_type=InputType.TAP, cam=1,
                mode=OperatingMode.USER, session_active=True,
                camera_available=window.Cam1._connected), lambda _: None)
            button.show()
            QTest.mouseClick(button, Qt.LeftButton)
            app.processEvents()
            check(panel._controls_widget.isVisible(), 'Seat recall hid PTZ controls')
        check(len(port.calls) == 5, 'Seat clicks did not dispatch five recalls')
        # A real control-channel cut may exceed the former 1.8 s hide grace.
        # The panel must stay spatially stable, while unsafe controls disable.
        window.Cam1._connected = False
        update_camera_controls_visibility(window)
        pump(2.05)
        check(panel._controls_widget.isVisible(), 'Transport cut longer than 1.8 s hid PTZ panel')
        check(not panel._motion_widget.isEnabled(), 'Disconnected motion controls remain enabled')
        check(panel._joystick.isVisible(), 'Joystick disappeared during control cut')
        check(not panel._joystick.isEnabled(), 'Disconnected joystick still accepts movement')
        check(panel._connection_status_label.isVisible(), 'Reconnect status is missing during control cut')
        import os
        screenshot = os.environ.get('KHPTZ_SELFTEST_SCREENSHOT')
        if screenshot:
            window.grab().save(screenshot)
        window.Cam1._connected = True
        update_camera_controls_visibility(window)
        app.processEvents()
        check(panel._controls_widget.isVisible(), 'Recovery did not preserve PTZ panel')
        check(panel._motion_widget.isEnabled(), 'Recovery did not re-enable motion controls')
        check(not panel._connection_status_label.isVisible(), 'Recovery left reconnect warning visible')
        return {'name': 'qt_seat_panel_regression', 'passed': True,
                'detail': '5 real Qt seat clicks; 2.05 s cut; stable panel and safe recovery'}
    finally:
        window.hide()
        window.deleteLater()
        app.processEvents()
