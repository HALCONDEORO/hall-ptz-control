"""Run isolated STOP regressions without leaking Qt stubs into test collection."""
from pathlib import Path
import subprocess
import sys


def test_emergency_stop_regressions_in_isolated_process():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / 'tests/focused_stop/regression.py'),
         '--tree', str(root)],
        cwd=root, capture_output=True, text=True, timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
