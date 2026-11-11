"""Recovery must not report completion when the provisioned service is down.

Execute the real post-start check with inert shell functions. No systemd,
backup, checkout, installer or host paths are changed.
"""
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runtime/installer/rollback.sh'


@pytest.mark.parametrize('provisioned,active,dev,dry,gui,expected', [
    (True, False, 'false', '0', 'system', 1),
    (True, True, 'false', '0', 'system', 0),
    (False, False, 'false', '0', 'system', 0),
    (False, False, 'true', '0', 'system', 1),
    (True, False, 'false', '1', 'system', 0),
    (True, False, 'false', '0', 'user', 0),
])
def test_post_start_check(tmp_path, provisioned, active, dev, dry, gui, expected):
    if provisioned:
        (tmp_path / '.provisioned').write_text('ok\n')
    source = SOURCE.read_text()
    start = source.index('if [[ "$DRY_RUN" != "1" && "$GUI_MODE" != "user" ]]; then')
    end = source.index('# Rollback completado', start)
    script = '\n'.join([
        'set -euo pipefail',
        'log() { printf "%s\\n" "$*"; }',
        'fail() { printf "%s\\n" "$*" >&2; exit 1; }',
        f'systemctl() {{ return {0 if active else 1}; }}',
        f'CONFIG_DIR={str(tmp_path)!r}',
        f'DRY_RUN={dry}; GUI_MODE={gui}; DEV_MODE={dev}; SERVICE_NAME=khptz-control',
        source[start:end],
        'echo ROLLBACK_COMPLETION_REACHED',
    ])
    result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
    assert result.returncode == expected, result.stdout + result.stderr
    assert ('ROLLBACK_COMPLETION_REACHED' in result.stdout) == (expected == 0)
    if expected:
        assert 'Service did not start' in result.stderr
