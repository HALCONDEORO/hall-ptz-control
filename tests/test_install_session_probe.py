"""The wrapper's desktop-session probe must distinguish active from inactive.

install_khptz_rpi.sh probes `loginctl show-user USER --property=State` to tell
the operator whether the desktop user has an active session. The probe used an
unanchored `grep -q "active"`, which also matches "State=inactive" — reporting
a logged-out user as active and suppressing the "GUI starts once the user logs
in" warning exactly when it applies. These tests run the REAL wrapper with
stub host commands, the same convention as test_install_unexpected_exit.py.
"""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "install_khptz_rpi.sh").read_text()


def _run_wrapper(tmp_path: Path, state: str) -> subprocess.CompletedProcess:
    wrapper = tmp_path / "install_khptz_rpi.sh"
    text = SOURCE.replace('if [[ "${EUID}" -ne 0 ]]; then', 'if false; then')
    wrapper.write_text(text)
    installer = tmp_path / "runtime/installer/install.sh"
    installer.parent.mkdir(parents=True)
    installer.write_text('#!/bin/bash\nexit 0\n')
    stubs = tmp_path / "bin"
    stubs.mkdir()
    for name, body in {
        'id': '[[ "$1" != "-u" ]] || echo 1000; exit 0',
        'getent': 'echo "desktop:x:1000:1000::/synthetic/home:/bin/bash"',
        'git': 'exit 1',
        'loginctl': f'[[ "$1" == "show-user" ]] && echo "State={state}"; exit 0',
        'systemctl': 'case "$1" in is-enabled) exit 1;; is-active) echo inactive; exit 3;; show) echo 0;; *) exit 0;; esac',
    }.items():
        command = stubs / name
        command.write_text('#!/bin/bash\n' + body + '\n')
        command.chmod(0o755)
    return subprocess.run(
        ['bash', str(wrapper), '--allow-dirty', '--wizard-user', 'desktop'],
        env=dict(os.environ, PATH=f'{stubs}:{os.environ["PATH"]}'),
        capture_output=True, text=True, timeout=10)


def test_active_state_reports_active_session(tmp_path):
    result = _run_wrapper(tmp_path, "active")
    assert "desktop has an active session" in result.stdout


@pytest.mark.parametrize("state", ["inactive", "lingering", "closing"])
def test_non_active_states_warn_not_report_active(tmp_path, state):
    result = _run_wrapper(tmp_path, state)
    assert "has an active session" not in result.stdout
    assert "has no active desktop session yet" in result.stderr
