#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Hardware-free MainWindow construction smoke test.

test_startup_smoke.py covers the non-UI path (bootstrap -> AppContext) but
explicitly does not build the MainWindow. This fills that gap: it constructs the
real MainWindow in simulation mode (no PTZ cameras, no ATEM, offscreen Qt) so
that every _build_* method — and, after #894, every ui/config_pages tab builder
reachable from construction — runs for real. It is the runtime net that turns
future MainWindow/ConfigDialog extraction from a static-only change into a
verifiable one: a NameError or a broken widget wiring in any build path aborts
this test instead of only surfacing on the Pi.

Per-test Qt widget cleanup comes from a conftest autouse fixture. These tests
run unforked (see the comment above the imports), so simulation mode is undone
by the sim_mode_active fixture rather than by process teardown.
"""

from __future__ import annotations

import sys

import pytest

from conftest import ensure_real_qt, is_poisoned_by_qt_stub

# NOT forked. Building a full real widget tree in a freshly forked child aborts
# (SIGABRT) inside Qt's offscreen platform init every time, even though the
# child is throwaway — the same failure that already forces
# test_setup_wizard.py and test_login_countdown_integration.py to run unforked
# (see the two pytest steps in .github/workflows/tests.yml). MainWindow builds
# the largest tree in the suite, so it runs in that second, unforked step and
# is excluded from the --forked run.

import adapters.sim_mode as sim_mode  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _real_qt():
    """Put the real PyQt5 in sys.modules before conftest's _qapp_available runs.

    That autouse fixture is a no-op when "PyQt5.QtWidgets" is not yet imported,
    and this module imports Qt lazily (inside the main_window fixture), so
    without this nothing would build a QApplication and QMainWindow.__init__
    would abort the process. It also drops any collection-time PyQt5 stub left
    by another module. Module-scoped fixtures run before function-scoped ones,
    so importing Qt here is enough for _qapp_available to do its job.
    """
    ensure_real_qt()


@pytest.fixture
def _qapp(_real_qt):
    """The process-wide QApplication, created on first use."""
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def sim_mode_active():
    """Run the body in simulation mode, then restore the previous state."""
    was_active = sim_mode.is_active()
    if not was_active:
        sim_mode.activate()
    try:
        yield
    finally:
        if not was_active:
            try:
                sim_mode.deactivate()
            except Exception:  # noqa: BLE001 — teardown must never fail the test
                pass


@pytest.fixture
def main_window(_qapp, sim_mode_active):
    """Construct the real MainWindow offscreen and close it afterwards."""
    from ui.main_window import MainWindow

    if is_poisoned_by_qt_stub(MainWindow):
        pytest.skip("ui.main_window was imported under a PyQt5 stub by another "
                    "test module — run this file in isolation")

    window = MainWindow()
    try:
        yield window
    finally:
        window.close()


def test_main_window_constructs_without_hardware(main_window):
    """All _build_* methods run during construction without raising."""
    # 475+ child widgets are built; assert the tree is non-trivial rather than
    # pinning an exact count that harmless layout tweaks would churn.
    assert len(main_window.findChildren(object)) > 100


def test_main_window_wires_the_camera_seam(main_window):
    """The #893 CameraConfigService seam and its collaborators exist."""
    assert main_window._camera_config is not None
    assert main_window._cameras is not None
    assert main_window._camera_port is not None


def test_main_window_session_starts_inactive(main_window):
    """Construction must not auto-start a session (lifecycle contract)."""
    assert main_window.session_active is False


def test_config_dialog_opens_from_main_window(main_window):
    """Building the split ConfigDialog (all ui/config_pages tabs) does not raise.

    This is the runtime check the #894 split could not get on its own: it forces
    every extracted tab builder to run against a real MainWindow.
    """
    from ui.config_dialog import ConfigDialog

    dialog = ConfigDialog(main_window)
    try:
        assert dialog.findChild(object) is not None
    finally:
        dialog.close()


def test_queued_zoom_rechecks_generation_on_qt_delivery(main_window, _qapp):
    from unittest.mock import Mock
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

    current = [1]
    main_window._camera_port.display_generation = lambda key: current[0]
    main_window._selected_cam_key = lambda: 1
    main_window._set_zoom_feedback = Mock()
    QMetaObject.invokeMethod(main_window, "_apply_zoom_feedback", Qt.QueuedConnection,
                             Q_ARG(int, 1), Q_ARG(int, 1), Q_ARG(int, 75))
    current[0] = 2  # Change after enqueue, before Qt delivers.
    _qapp.processEvents()
    main_window._set_zoom_feedback.assert_not_called()


def test_queued_zoom_drops_result_after_camera_selection_changes(main_window, _qapp):
    from unittest.mock import Mock
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

    main_window._camera_port.display_generation = lambda key: 0
    selected = [1]
    main_window._selected_cam_key = lambda: selected[0]
    main_window._set_zoom_feedback = Mock()
    QMetaObject.invokeMethod(main_window, "_apply_zoom_feedback", Qt.QueuedConnection,
                             Q_ARG(int, 1), Q_ARG(int, 0), Q_ARG(int, 75))
    selected[0] = 2
    _qapp.processEvents()
    main_window._set_zoom_feedback.assert_not_called()


def test_queued_exposure_rechecks_generation_on_qt_delivery(main_window, _qapp):
    from unittest.mock import Mock
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

    current = [1]
    main_window._camera_port.display_generation = lambda key: current[0]
    main_window._selected_cam_key = lambda: 1
    main_window._update_exposure_ui = Mock()
    QMetaObject.invokeMethod(main_window, "_apply_exposure_update", Qt.QueuedConnection,
                             Q_ARG(int, 1), Q_ARG(int, 1))
    current[0] = 2
    _qapp.processEvents()
    main_window._update_exposure_ui.assert_not_called()


def test_retired_worker_connection_does_not_query_camera_one(main_window):
    from unittest.mock import Mock

    main_window._camera_port.async_refresh_ae_mode = Mock()
    main_window._cameras.cam_key = Mock(side_effect=ValueError("retired endpoint"))
    main_window._on_cam_connected(True, "192.0.2.99")
    main_window._camera_port.async_refresh_ae_mode.assert_not_called()


def test_current_queued_display_updates_are_delivered(main_window, _qapp):
    from unittest.mock import Mock
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

    main_window._camera_port.display_generation = lambda key: 3
    main_window._selected_cam_key = lambda: 1
    main_window._set_zoom_feedback = Mock()
    main_window._update_exposure_ui = Mock()
    QMetaObject.invokeMethod(main_window, "_apply_zoom_feedback", Qt.QueuedConnection,
                             Q_ARG(int, 1), Q_ARG(int, 3), Q_ARG(int, 75))
    QMetaObject.invokeMethod(main_window, "_apply_exposure_update", Qt.QueuedConnection,
                             Q_ARG(int, 1), Q_ARG(int, 3))
    _qapp.processEvents()
    main_window._set_zoom_feedback.assert_called_once_with(75)
    main_window._update_exposure_ui.assert_called_once()


def test_seat_save_cannot_follow_camera_selection_change(main_window, monkeypatch):
    from unittest.mock import Mock
    # This regression concerns preset targeting, not background display reads.
    monkeypatch.setattr(main_window._camera_port, "refresh_zoom_display", Mock())
    monkeypatch.setattr(main_window._camera_port, "async_refresh_ae_mode", Mock())
    main_window.Cam2.click()
    main_window._enter_seat_selection(37)
    main_window.Cam1.click()
    main_window._bus = Mock()
    main_window._exit_seat_selection(save=True)
    main_window._bus.emit.assert_not_called()
    assert main_window._seat_pending is None
    assert not main_window._btn_save_seat.isVisible()


def test_seat_save_keeps_selected_camera_when_unchanged(main_window, monkeypatch):
    from unittest.mock import Mock
    # This regression concerns preset targeting, not background display reads.
    monkeypatch.setattr(main_window._camera_port, "refresh_zoom_display", Mock())
    monkeypatch.setattr(main_window._camera_port, "async_refresh_ae_mode", Mock())
    from core.events import EventType
    main_window.Cam2.click()
    main_window._enter_seat_selection(37)
    main_window._bus = Mock()
    main_window._exit_seat_selection(save=True)
    main_window._bus.emit.assert_called_once_with(
        EventType.PRESET_SAVE_SLOT, camera=2, slot=37,
    )


def test_cancelled_seat_selection_cannot_be_saved_later(main_window, monkeypatch):
    from unittest.mock import Mock
    # This regression concerns preset targeting, not background display reads.
    monkeypatch.setattr(main_window._camera_port, "refresh_zoom_display", Mock())
    monkeypatch.setattr(main_window._camera_port, "async_refresh_ae_mode", Mock())
    main_window._enter_seat_selection(37)
    main_window._bus = Mock()
    main_window._exit_seat_selection(save=False)
    main_window._exit_seat_selection(save=True)
    main_window._bus.emit.assert_not_called()


def test_custom_special_seat_builds_without_known_legacy_icon(main_window, monkeypatch):
    """A valid custom special layout must not abort construction with KeyError."""
    from domain.room_layout import SeatLayout
    from ui.widgets import SpecialDragButton

    seat = SeatLayout(id="side", label="Side room", preset=37,
                      camera_role="comments", x=10, y=20, type="special")
    monkeypatch.setattr(main_window._layout_svc, "visible_seats", lambda: [seat])
    main_window._build_seat_buttons()
    button = main_window.Seat37
    assert isinstance(button, SpecialDragButton)
    assert button.seat_number == 37
    assert button.text() == "Side room"
    assert button.x() == 10 and button.y() == 20
    assert button.icon().isNull()


@pytest.mark.parametrize("transition", ["unchanged", "ended", "restarted", "closing", "rejected"])
def test_platform_save_confirmation_stays_in_its_session(main_window, monkeypatch, transition):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PyQt5.QtWidgets import QMessageBox
    from core.events import EventType
    from domain.call_set_policy import InputType

    main_window._camera_port.refresh_zoom_display = Mock()
    main_window._camera_port.async_refresh_ae_mode = Mock()
    main_window.session_active = True
    main_window._app_ctrl = Mock()
    main_window._app_ctrl.recall_seat.return_value = SimpleNamespace(error_code="set_action")
    main_window._bus = Mock()

    def confirm_after_transition(*args, **kwargs):
        if transition in ("ended", "restarted"):
            main_window._session.shutdown("inactivity")
            if transition == "restarted":
                main_window._session.ToggleSession()
        elif transition == "closing":
            main_window._shutting_down = True
        main_window._bus.reset_mock()
        return QMessageBox.No if transition == "rejected" else QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm_after_transition)
    main_window._dispatch_preset_action(1, InputType.LONG_PRESS)
    if transition == "unchanged":
        main_window._bus.emit.assert_called_once_with(EventType.PRESET_SAVE_SLOT, camera=1, slot=1)
    else:
        main_window._bus.emit.assert_not_called()


@pytest.mark.parametrize("deleted", [False, True])
def test_right_panel_fit_handles_container_lifetime(_qapp, deleted):
    from PyQt5 import sip
    from PyQt5.QtWidgets import QFrame
    from ui.right_panel import RightPanel

    panel = RightPanel.__new__(RightPanel)
    panel._container = QFrame()
    if deleted:
        sip.delete(panel._container)
    # A queued fit can outlive its parent widget during window teardown.
    panel._fit_container_height()
    if not deleted:
        assert panel._container.geometry().getRect() == (1446, 0, 474, 1080)


@pytest.mark.parametrize("deleted", [False, True])
def test_right_panel_flash_handles_button_lifetime(_qapp, monkeypatch, deleted):
    from PyQt5 import sip
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QPushButton
    from ui.right_panel import RightPanel

    callbacks = []
    monkeypatch.setattr(QTimer, "singleShot", lambda delay, callback: callbacks.append(callback))
    panel = RightPanel.__new__(RightPanel)
    panel._btn_focus_base_style = "QPushButton { color: black; }"
    button = QPushButton()
    panel._flash_button(button, True)
    if deleted:
        sip.delete(button)
    callbacks[0]()
    if not deleted:
        assert button.styleSheet() == panel._btn_focus_base_style


@pytest.mark.parametrize("deleted", [False, True])
def test_main_window_blocked_flash_handles_button_lifetime(_qapp, monkeypatch, deleted):
    from PyQt5 import sip
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QPushButton
    from ui.main_window import MainWindow

    callbacks = []
    monkeypatch.setattr(QTimer, "singleShot", lambda delay, callback: callbacks.append(callback))
    button = QPushButton()
    button.setStyleSheet("QPushButton { color: black; }")
    original = button.styleSheet()
    MainWindow._flash_blocked(None, button)
    if deleted:
        sip.delete(button)
    callbacks[0]()
    if not deleted:
        assert button.styleSheet() == original


def test_session_end_cancels_unconfirmed_seat_save(main_window, monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(main_window._camera_port, "refresh_zoom_display", Mock())
    monkeypatch.setattr(main_window._camera_port, "async_refresh_ae_mode", Mock())
    main_window._enter_seat_selection(37)
    main_window._bus = Mock()
    main_window._session.shutdown("manual")
    assert main_window._seat_pending is None
    assert main_window._seat_pending_camera is None
    main_window._bus.reset_mock()
    main_window.session_active = True  # a later session must not inherit Save
    main_window._exit_seat_selection(save=True)
    main_window._bus.emit.assert_not_called()


@pytest.mark.parametrize("kind", ["zoom", "exposure"])
def test_late_display_callback_ignores_destroyed_window(_qapp, kind):
    """A completed network read may outlive the window receiving its result."""
    from unittest.mock import Mock
    from PyQt5 import sip
    from PyQt5.QtWidgets import QWidget
    from ui.camera_display_mixin import CameraDisplayMixin

    class DisplayWindow(CameraDisplayMixin, QWidget):
        pass

    window = DisplayWindow()
    window.Cam1 = Mock()
    window.Cam1.isChecked.return_value = True
    window._camera_port = Mock()
    window._camera_port.display_generation.return_value = 0
    window._cameras = Mock()
    window._cameras.cam_key.return_value = 1
    if kind == "zoom":
        window._refresh_zoom()
        callback = window._camera_port.refresh_zoom_display.call_args.args[1]
    else:
        window._on_cam_connected(True, "192.0.2.1")
        callback = window._camera_port.async_refresh_ae_mode.call_args.args[1]
    sip.delete(window)
    if kind == "zoom":
        callback(50)
    else:
        callback()


@pytest.mark.parametrize("kind", ["zoom", "exposure"])
def test_display_callback_still_delivers_to_live_receiver(_qapp, kind):
    from unittest.mock import Mock
    from PyQt5.QtWidgets import QWidget
    from ui.camera_display_mixin import CameraDisplayMixin

    class DisplayWindow(CameraDisplayMixin, QWidget):
        pass

    window = DisplayWindow()
    window.Cam1 = Mock()
    window.Cam1.isChecked.return_value = True
    window._camera_port = Mock()
    window._camera_port.display_generation.return_value = 0
    window._cameras = Mock()
    window._cameras.cam_key.return_value = 1
    window._set_zoom_feedback = Mock()
    window._update_exposure_ui = Mock()
    if kind == "zoom":
        window._refresh_zoom()
        window._camera_port.refresh_zoom_display.call_args.args[1](50)
        _qapp.processEvents()
        window._set_zoom_feedback.assert_called_once_with(50)
    else:
        window._on_cam_connected(True, "192.0.2.1")
        window._camera_port.async_refresh_ae_mode.call_args.args[1]()
        _qapp.processEvents()
        window._update_exposure_ui.assert_called_once_with()
    window.close()


@pytest.mark.parametrize("kind", ["zoom", "exposure"])
def test_queued_display_update_is_dropped_after_shutdown(_qapp, kind):
    from unittest.mock import Mock
    from PyQt5.QtWidgets import QWidget
    from ui.camera_display_mixin import CameraDisplayMixin

    class DisplayWindow(CameraDisplayMixin, QWidget):
        pass

    window = DisplayWindow()
    window.Cam1 = Mock()
    window.Cam1.isChecked.return_value = True
    window._camera_port = Mock()
    window._camera_port.display_generation.return_value = 0
    window._cameras = Mock()
    window._cameras.cam_key.return_value = 1
    window._set_zoom_feedback = Mock()
    window._update_exposure_ui = Mock()
    if kind == "zoom":
        window._refresh_zoom()
        callback = window._camera_port.refresh_zoom_display.call_args.args[1]
        callback(50)
    else:
        window._on_cam_connected(True, "192.0.2.1")
        callback = window._camera_port.async_refresh_ae_mode.call_args.args[1]
        callback()
    window._shutting_down = True
    _qapp.processEvents()
    window._set_zoom_feedback.assert_not_called()
    window._update_exposure_ui.assert_not_called()
    window.close()


@pytest.mark.parametrize("transition", ["ended", "restarted", "restarted_and_ended", "closing"])
def test_delayed_screen_sleep_belongs_to_ended_session(main_window, monkeypatch, transition):
    from unittest.mock import Mock
    from PyQt5.QtCore import QTimer
    import ui.main_window as module

    main_window._camera_port.refresh_zoom_display = Mock()
    main_window._camera_port.async_refresh_ae_mode = Mock()
    main_window._bus = Mock()
    main_window.session_active = True
    dialog = Mock()
    dialog.exec_.return_value = 1
    factory = Mock(return_value=dialog)
    factory.Accepted = 1
    monkeypatch.setattr(module, "ScreenOffDialog", factory)
    sleep = Mock()
    monkeypatch.setattr(module.ScreenMonitor, "sleep", sleep)
    monkeypatch.setattr(module.ScreenMonitor, "wake", Mock())
    callbacks = []
    monkeypatch.setattr(QTimer, "singleShot", lambda delay, callback: callbacks.append((delay, callback)))

    main_window._on_screen_turned_off()
    sleep_callback = next(callback for delay, callback in callbacks if delay == 1500)
    if transition in ("restarted", "restarted_and_ended"):
        main_window._session.ToggleSession()
        if transition == "restarted_and_ended":
            main_window._session.shutdown("manual")
    elif transition == "closing":
        main_window._shutting_down = True
    sleep_callback()

    if transition == "ended":
        sleep.assert_called_once_with()
    else:
        sleep.assert_not_called()
