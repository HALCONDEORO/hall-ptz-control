"""Run the installed self-test scenario in a clean real-Qt process."""
import os
from pathlib import Path
import subprocess
import sys


def test_camera_panel_scenario_covers_long_cut_without_hidden_controls():
    result = subprocess.run([sys.executable, '-c',
        'from runtime.selftest_support.panel import run_panel_check; print(run_panel_check())'],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
