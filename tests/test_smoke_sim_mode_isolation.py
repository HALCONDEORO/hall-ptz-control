"""test_main_window_smoke.py must not write appliance config into the checkout.

sim_mode's app dir defaults to the repository root, so the smoke file's
sim_mode_active fixture used to write sim_ip_backup.json and simulator
PTZ1IP/PTZ2IP.txt into the checkout on activate(), and rewrite
PTZ1IP/PTZ2IP/ATEMIP.txt from the backup on deactivate() - every run left an
untracked empty ATEMIP.txt (and, on a real appliance checkout, a crashed run
would have left simulator IPs in the live camera config). The fixture now
redirects sim_mode storage into a tmp dir; this test proves a smoke run leaves
the repository root untouched.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("PyQt5") is None,
    reason="the smoke file needs real PyQt5",
)


def test_smoke_run_leaves_no_config_artifacts_in_repo_root():
    for name in ("ATEMIP.txt", "PTZ1IP.txt", "PTZ2IP.txt", "sim_ip_backup.json"):
        (ROOT / name).unlink(missing_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_main_window_smoke.py", "-k", "constructs"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("ATEMIP.txt", "PTZ1IP.txt", "PTZ2IP.txt", "sim_ip_backup.json"):
        assert not (ROOT / name).exists(), f"{name} leaked into the repo root"
