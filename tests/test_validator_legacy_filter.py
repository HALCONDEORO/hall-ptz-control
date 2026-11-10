"""Execute the deployment validator's actual filter with synthetic argv rows."""
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/validate_rpi_deployment.sh'


def filtered(rows):
    text = SCRIPT.read_text()
    start = text.index('filter_legacy_processes() {')
    end = text.index('\nLEGACY_PROCS=', start)
    result = subprocess.run(
        ['bash', '-c', "set -Eeuo pipefail\nIFS=$'\\n\\t'\n" + text[start:end] + '\nfilter_legacy_processes'],
        input=rows, text=True, capture_output=True, check=True,
    )
    return result.stdout


@pytest.mark.parametrize('python', ['/usr/bin/python3', 'python3', '/usr/bin/python3.11'])
def test_supported_gui_is_not_legacy(python):
    assert filtered(f'123 {python} /opt/khptz/main.py --profile production\n') == ''


def test_mixed_processes_keep_legacy_and_exclude_only_supported_gui():
    legacy = '125 /usr/bin/python3 /home/operator/hallptz/main.py\n'
    rows = '123 /usr/bin/python3 /opt/khptz/main.py\n' + legacy
    assert filtered(rows) == legacy


def test_legacy_cannot_hide_by_using_canonical_path_as_an_extra_argument():
    row = '125 /usr/bin/python3 /home/operator/khptz/old.py /opt/khptz/main.py\n'
    assert filtered(row) == row


def test_similarly_named_script_is_not_exempted():
    row = '125 /usr/bin/python3 /opt/khptz/main.py.old\n'
    assert filtered(row) == row


@pytest.mark.parametrize('count, verdict', [(0, 'FAIL'), (1, 'OK'), (2, 'FAIL')])
def test_actual_gui_count_block(count, verdict):
    text = SCRIPT.read_text()
    start = text.index('KHPTZ_PROCS=')
    end = text.index('\n# khptz-control.service active.', start)
    rows = ''.join(f'{123 + n} /usr/bin/python3 /opt/khptz/main.py\n' for n in range(count))
    harness = """
set -Eeuo pipefail
IFS=$'\\n\\t'
pgrep() { cat; }
ok() { printf 'OK %s\\n' "$*"; }
bad() { printf 'FAIL %s\\n' "$*"; }
"""
    result = subprocess.run(
        ['bash', '-c', harness + text[start:end]],
        input=rows, capture_output=True, text=True, check=True,
    )
    assert result.stdout.startswith(verdict + ' ')
    if count == 2:
        assert '2 KHPTZ GUI processes' in result.stdout
        assert filtered(rows) == ''


def test_validator_and_parent_pid_are_excluded_under_actual_shell_settings():
    text = SCRIPT.read_text()
    start = text.index('filter_legacy_processes() {')
    end = text.index('\nLEGACY_PROCS=', start)
    command = (
        "set -Eeuo pipefail\nIFS=$'\\n\\t'\n" + text[start:end]
        + """
printf '%s bash validator\n%s sudo validator\n125 python3 /home/old/khptz.py\n' "$$" "$PPID" | filter_legacy_processes
"""
    )
    result = subprocess.run(['bash', '-c', command], capture_output=True, text=True, check=True)
    assert result.stdout == '125 python3 /home/old/khptz.py\n'
