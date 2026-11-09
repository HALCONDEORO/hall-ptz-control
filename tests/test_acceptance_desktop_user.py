"""Behavioral tests for the acceptance harness's desktop-user resolution and
session-type check.

Review context: without SUDO_USER (acceptance run from a plain terminal) the
session check used to SKIP outright even when loginctl could see an active
Wayland session - the hall could be signed off on a desktop that can never
show the GUI. The script now resolves the desktop user from explicit state
first (--wizard-user, then KHPTZ_WIZARD_USER in the install-state file),
then the ambient environment (SUDO_USER, invoking non-root user), and must
still reach the right verdict with no SUDO_USER at all.

The real validate_rpi_acceptance.sh runs end to end here with a stubbed
``id``/``loginctl`` pair; only the "Desktop session" section of the report
is asserted, so unrelated sections cannot make the verdicts flaky.
"""

import stat
import subprocess
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_rpi_acceptance.sh"

ID_STUB = """#!/bin/bash
# id stub: FAKE_UID controls `id -u` with no argument (0 = pretend root, so
# the invoking-user fallback stays out of the way); KNOWN_USERS is the
# space-separated list of accounts that exist.
if [[ "$1" == "-u" && -n "${2:-}" ]]; then
    case " ${KNOWN_USERS:-wizard} " in
        *" $2 "*) echo 1000; exit 0 ;;
        *) echo "id: '$2': no such user" >&2; exit 1 ;;
    esac
elif [[ "$1" == "-u" ]]; then
    echo "${FAKE_UID:-0}"; exit 0
elif [[ "$1" == "-un" ]]; then
    echo root; exit 0
fi
exit 1
"""

LOGINCTL_STUB = """#!/bin/bash
# loginctl stub driven by a fixture file of "sid type active user" lines.
fx="${LOGINCTL_FIXTURE:?}"
case "$1" in
    list-sessions)
        while read -r sid type active user; do
            [[ -n "${sid}" ]] && printf ' %s 1000 %s seat0\\n' "${sid}" "${user}"
        done < "${fx}"
        ;;
    show-session)
        sid="$2"; prop=""; shift 2
        while [[ $# -gt 0 ]]; do
            case "$1" in --property=*) prop="${1#--property=}" ;; esac
            shift
        done
        while read -r s t a u; do
            if [[ "${s}" == "${sid}" ]]; then
                case "${prop}" in
                    Type) echo "${t}" ;;
                    Active) echo "${a}" ;;
                esac
            fi
        done < "${fx}"
        ;;
esac
exit 0
"""


def _write_exe(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_acceptance(tmp_path: Path, fixture: Optional[str], with_loginctl: bool = True,
                    extra_env: Optional[dict] = None) -> str:
    stubbin = tmp_path / "bin"
    stubbin.mkdir(exist_ok=True)
    _write_exe(stubbin / "id", ID_STUB)
    if with_loginctl:
        _write_exe(stubbin / "loginctl", LOGINCTL_STUB)
    # A private PATH so the machine's own loginctl (if any) cannot leak in:
    # the "no loginctl" case must exercise the truly-absent branch.
    sysbin = tmp_path / "sysbin"
    sysbin.mkdir(exist_ok=True)
    for d in ("/usr/bin", "/bin"):
        p = Path(d)
        if not p.is_dir():
            continue
        for tool in p.iterdir():
            if tool.name == "loginctl":
                continue
            dest = sysbin / tool.name
            if not dest.exists():
                dest.symlink_to(tool)
    fx = tmp_path / "sessions.fixture"
    fx.write_text(fixture or "")
    state = tmp_path / "install-state.env"
    state.write_text('KHPTZ_WIZARD_USER="wizard"\n')
    report = tmp_path / "report.txt"

    env = {
        "PATH": f"{stubbin}:{sysbin}",
        "HOME": str(tmp_path),
        "LOGINCTL_FIXTURE": str(fx),
        "KHPTZ_STATE_FILE": str(state),
        "FAKE_UID": "0",
    }
    if extra_env:
        env.update(extra_env)

    subprocess.run(
        ["bash", str(SCRIPT), "--report", str(report)],
        env=env, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    return report.read_text()


def _desktop_section(report: str) -> str:
    start = report.index("== Desktop session ==")
    end = report.find("== ", start + 10)
    return report[start:] if end == -1 else report[start:end]


@pytest.fixture
def state_file():
    return 'KHPTZ_WIZARD_USER="wizard"\n'


class TestDesktopUserResolution:
    """Mejora's four cases, all run with SUDO_USER absent."""

    def test_no_sudo_user_active_wayland_fails(self, tmp_path):
        report = _run_acceptance(tmp_path, "3 wayland yes wizard\n")
        section = _desktop_section(report)
        assert "[FAIL]" in section
        assert "Wayland" in section
        assert "user from install state" in section
        assert "raspi-config" in section

    def test_no_sudo_user_active_x11_passes(self, tmp_path):
        report = _run_acceptance(tmp_path, "3 x11 yes wizard\n")
        section = _desktop_section(report)
        assert "[PASS]" in section
        assert "X11" in section
        assert "from install state" in section

    def test_no_sudo_user_inactive_session_skips(self, tmp_path):
        report = _run_acceptance(tmp_path, "3 wayland no wizard\n")
        section = _desktop_section(report)
        assert "[SKIP]" in section
        assert "no active graphical session" in section

    def test_no_sudo_user_no_loginctl_skips(self, tmp_path):
        report = _run_acceptance(tmp_path, None, with_loginctl=False)
        section = _desktop_section(report)
        assert "[SKIP]" in section
        assert "loginctl" in section

    def test_install_state_wins_over_sudo_user(self, tmp_path):
        # SUDO_USER points at another account; the installer's recorded
        # wizard user must win, and the report must say so.
        report = _run_acceptance(
            tmp_path, "3 x11 yes wizard\n4 wayland yes other\n",
            extra_env={"SUDO_USER": "other", "KNOWN_USERS": "wizard other"},
        )
        section = _desktop_section(report)
        assert "[PASS]" in section
        assert "user wizard from install state" in section


class TestMissingOptionValues:
    """A value-taking flag without its value used to hang forever: `shift 2`
    on a single remaining argument fails silently (no set -e), the loop never
    advances, and CI/timeout is the only way out. The validator must exit 2
    with a usage message instead - for both the new --wizard-user and the
    pre-existing --report, which shared the shape."""

    @pytest.mark.parametrize("flag", ["--report", "--wizard-user"])
    def test_missing_value_exits_2_not_hang(self, flag, tmp_path):
        result = subprocess.run(
            ["timeout", "10", "bash", str(SCRIPT), flag],
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 2, (
            f"expected exit 2, got {result.returncode} "
            f"(124 would mean the parser hung): {result.stderr}"
        )
        assert "needs a value" in result.stderr

    @pytest.mark.parametrize("flag", ["--report", "--wizard-user"])
    def test_option_looking_value_is_rejected(self, flag, tmp_path):
        result = subprocess.run(
            ["timeout", "10", "bash", str(SCRIPT), flag, "--check"],
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 2
        assert "needs a value" in result.stderr
