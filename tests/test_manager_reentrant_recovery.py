# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""A completion callback during recovery may inspect current camera state."""
import os
from pathlib import Path
import subprocess
import sys


def test_restart_callback_can_read_manager_without_deadlock():
    code = '''
from types import SimpleNamespace
from unittest.mock import Mock
from ptz.visca.manager import CameraManager
manager = CameraManager(SimpleNamespace(ip="192.0.2.1",cam_id="81"),
                        SimpleNamespace(ip="192.0.2.2",cam_id="82"))
worker = Mock()
worker.is_connected = True
# Worker restart may notify a discarded command's completion callback.
# Reading status from that callback must not re-enter a non-reentrant lock.
worker.restart.side_effect = lambda: manager.is_connected("192.0.2.1")
manager._workers["192.0.2.1"] = worker
assert manager.restart_worker(1) is True
worker.restart.assert_called_once_with()
'''
    result = subprocess.run([sys.executable, "-c", code],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                            capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stdout + result.stderr
