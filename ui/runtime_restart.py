"""Defer profile changes and process launch until close is confirmed."""
import os
from pathlib import Path
import subprocess
import sys

from adapters import sim_mode


def queue_runtime_restart(dialog, window, target_mode):
    main_path = Path(__file__).resolve().parent.parent / 'main.py'
    if not main_path.is_file():
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(dialog, 'Restart failed', 'Application entry point is missing.')
        return

    def prepare():
        from PyQt5.QtWidgets import QMessageBox
        title = f'Restart in {target_mode.title()} Mode'
        demo_dir = Path.home() / '.config' / 'khptz-demo'
        if target_mode == "production":
            try:
                if sim_mode.is_active():
                    sim_mode.deactivate()
            except RuntimeError as exc:
                QMessageBox.warning(
                    dialog,
                    title,
                    str(exc) or "Could not disable simulation mode.",
                )
                return
        else:
            if target_mode == "demo":
                try:
                    from application.demo_reset_service import DemoResetService

                    result = DemoResetService(demo_data_dir=demo_dir).reset()
                except Exception as exc:
                    QMessageBox.warning(
                        dialog,
                        title,
                        f"Could not reset demo data:\n{exc}",
                    )
                    return

                if not result.success:
                    QMessageBox.warning(
                        dialog,
                        title,
                        result.error or "Could not reset demo data.",
                    )
                    return

            try:
                if not sim_mode.is_active():
                    sim_mode.activate()
            except RuntimeError as exc:
                QMessageBox.warning(
                    dialog,
                    title,
                    str(exc) or "Could not enable simulation mode.",
                )
                return

        env = os.environ.copy()
        env["KHPTZ_PROFILE"] = target_mode
        if target_mode in {"demo", "simulation"}:
            env["KHPTZ_DATA_DIR"] = str(demo_dir)
        elif Path(env.get("KHPTZ_DATA_DIR", "")).expanduser() == demo_dir:
            env.pop("KHPTZ_DATA_DIR", None)

        window._pending_admin_restart_env = env
        return True

    window._pending_admin_restart = [sys.executable, str(main_path)]
    window._pending_admin_restart_cwd = str(main_path.parent)
    window._pending_runtime_prepare = prepare
    if window.close():
        dialog.close()
    else:
        clear_runtime_restart(window)


def clear_runtime_restart(window):
    window._pending_runtime_prepare = None
    window._pending_admin_restart_env = None
    window._pending_admin_restart = None


def prepare_runtime_restart(window):
    prepare = getattr(window, '_pending_runtime_prepare', None)
    if prepare is None:
        return True
    window._pending_runtime_prepare = None
    if prepare():
        return True
    clear_runtime_restart(window)
    return False


def launch_pending_restart(window):
    subprocess.Popen(window._pending_admin_restart,
                     cwd=window._pending_admin_restart_cwd,
                     env=getattr(window, '_pending_admin_restart_env', None),
                     close_fds=True)
