"""Run the installer parser without reaching host checks or write operations."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "runtime/installer/install.sh"


@pytest.fixture
def parser_script(tmp_path):
    text = SCRIPT.read_text(encoding="utf-8")
    boundary = '# The setup wizard runs in the desktop session as this user;'
    assert text.count(boundary) == 1
    # The real parser is verbatim. Exit before runtime setup, root checks,
    # dependencies or any install operation, even on a privileged test runner.
    parser = tmp_path / "parse.sh"
    parser.write_text(text.split(boundary)[0] + '\nprintf "CHECK_MODE=%s\\n" "$CHECK_MODE"\n',
                      encoding="utf-8")
    return parser


pytestmark = pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32",
                                reason="requires native POSIX bash")


@pytest.mark.parametrize("args", [
    ["--wizard-user"],
    ["--wizard-user", ""],
    ["--wizard-user", "--check"],
    ["--wizard-user", "--dev"],
    ["--wizard-user", "--atem"],
])
def test_missing_wizard_username_is_rejected_before_host_access(parser_script, args):
    result = subprocess.run(["bash", str(parser_script), *args],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "--wizard-user requires a username" in result.stderr
    assert "CHECK_MODE=" not in result.stdout


def test_valid_username_does_not_consume_check_flag(parser_script):
    result = subprocess.run(["bash", str(parser_script), "--wizard-user", "desktop", "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CHECK_MODE=true" in result.stdout
