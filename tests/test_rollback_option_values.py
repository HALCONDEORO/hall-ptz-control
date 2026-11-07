"""Malformed options must stop before preflight, backups or service changes."""
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'runtime/installer/rollback.sh'


@pytest.mark.parametrize('option', ['--user', '--dir', '--source', '--to'])
@pytest.mark.parametrize('value', [None, '', '--dry-run'])
def test_value_options_reject_missing_empty_or_flag_value(option, value):
    args = ['bash', str(SCRIPT), option]
    if value is not None:
        args.append(value)
    result = subprocess.run(args, capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert f'{option} requires a value' in result.stderr
    assert 'unbound variable' not in result.stderr
    assert 'Step 1:' not in result.stdout
    assert 'Install directory not found' not in result.stderr
