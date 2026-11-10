# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Exercise the production dialog-opening method without unrelated GUI startup."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def open_settings_method(cam1, cam2, dialog, forbidden_probe):
    source = Path("ui/main_window.py").read_text()
    tree = ast.parse(source)
    window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    method = next(n for n in window.body if isinstance(n, ast.FunctionDef) and n.name == "_open_config_dialog")
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {"CAM1": cam1, "CAM2": cam2, "ConfigDialog": dialog,
                 "check_all_cameras": forbidden_probe}
    exec(compile(ast.fix_missing_locations(module), "ui/main_window.py", "exec"), namespace)
    return namespace["_open_config_dialog"]


def test_opening_settings_uses_existing_transport_state_without_second_session():
    cam1 = SimpleNamespace(ip="192.0.2.1", check="Red")
    cam2 = SimpleNamespace(ip="192.0.2.2", check="Green")
    dialog = Mock()
    forbidden_probe = Mock(side_effect=AssertionError("Settings must not open new TCP sessions"))
    window = SimpleNamespace(
        _cameras=SimpleNamespace(is_connected=Mock(side_effect=[True, False])),
        _right_panel=SimpleNamespace(_update_mode_buttons=Mock()))
    open_settings_method(cam1, cam2, dialog, forbidden_probe)(window)
    forbidden_probe.assert_not_called()
    assert cam1.check == "Green"
    assert cam2.check == "Red"
    assert window._cameras.is_connected.call_args_list == [(("192.0.2.1",),), (("192.0.2.2",),)]
    dialog.assert_called_once_with(parent=window)
    dialog.return_value.exec_.assert_called_once_with()
    window._right_panel._update_mode_buttons.assert_called_once_with()
