"""Unexpected exit reporting must be additive, bounded and preserve status."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "install_khptz_rpi.sh").read_text()
HELPERS = SOURCE[SOURCE.index("INSTALL_STARTED=false"):SOURCE.index("# ── Arguments")]


@pytest.mark.parametrize("started", ["true", "false"])
@pytest.mark.parametrize("code", [1, 7, 126, 130, 143])
def test_unexpected_exit_preserves_original_code_and_first_error(started, code):
    script = ('set -euo pipefail\n' + HELPERS + f'\nINSTALL_STARTED={started}\n'
              'echo "ORIGINAL ERROR" >&2\n' + f'(exit {code})\necho SHOULD_NOT_RUN')
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == code
    assert result.stderr.startswith("ORIGINAL ERROR")
    assert result.stderr.count("Siguiente paso:") == 1
    assert "SHOULD_NOT_RUN" not in result.stdout
    if started == "true":
        assert "cambios parciales" in result.stderr
    else:
        assert "no habia iniciado" in result.stderr


def test_explicit_fatal_already_explains_failure_once():
    result = subprocess.run(["bash", "-c", HELPERS + '\nfatal "fixture"'],
                            capture_output=True, text=True)
    assert result.returncode == 30
    assert result.stderr.count("Siguiente paso:") == 1
    assert "antes del resumen" not in result.stderr


@pytest.mark.parametrize("code", [0, 20, 30])
def test_expected_completion_never_adds_misleading_error(code):
    script = HELPERS + f'\nFAILURE_REPORTED=true\nexit {code}'
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == code
    assert result.stderr == ""


def test_full_wrapper_cleanup_failure_preserves_cause_and_stops_before_diagnostics(tmp_path):
    """Real wrapper, inert host/installer, injected cleanup error. No host writes."""
    wrapper = tmp_path / "install_khptz_rpi.sh"
    marker = tmp_path / "old-display.conf"
    marker.write_text("synthetic")
    text = SOURCE.replace('if [[ "${EUID}" -ne 0 ]]; then', 'if false; then')
    text = text.replace('DROPIN_FILE="${DROPIN_DIR}/10-display-session.conf"',
                        f'DROPIN_FILE={str(marker)!r}')
    wrapper.write_text(text)
    installer = tmp_path / "runtime/installer/install.sh"
    installer.parent.mkdir(parents=True)
    installer.write_text('#!/bin/bash\necho "SYNTHETIC child ${*}"\nexit 0\n')
    stubs = tmp_path / "bin"
    stubs.mkdir()
    for name, body in {
        'id': '[[ "$1" != "-u" ]] || echo 1000; exit 0',
        'getent': 'echo "desktop:x:1000:1000::/synthetic/home:/bin/bash"',
        'git': 'exit 1', 'loginctl': 'exit 1',
        'rm': 'echo "ORIGINAL cleanup denied" >&2; exit 7',
        'systemctl': 'echo "UNEXPECTED systemctl" >&2; exit 99',
        'sudo': 'echo "UNEXPECTED sudo" >&2; exit 99',
    }.items():
        command = stubs / name
        command.write_text('#!/bin/bash\n' + body + '\n')
        command.chmod(0o755)
    result = subprocess.run(['bash', str(wrapper), '--allow-dirty', '--wizard-user', 'desktop'],
                            env=dict(os.environ, PATH=f'{stubs}:{os.environ["PATH"]}'),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 7
    assert 'ORIGINAL cleanup denied' in result.stderr
    assert 'cambios parciales' in result.stderr
    assert result.stderr.count('Siguiente paso:') == 1
    assert 'UNEXPECTED' not in result.stderr
    assert 'Comprobando la instalacion con el diagnostico' not in result.stdout
    assert marker.read_text() == 'synthetic'
