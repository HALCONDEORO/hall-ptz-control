"""Run actual validator helpers with synthetic uid/sudo commands, never sudo."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ['validate_rpi_deployment.sh', 'validate_rpi_acceptance.sh']


def helper(script):
    text = (ROOT / 'scripts' / script).read_text()
    start = text.index('cli_as_service() {')
    end = text.index('\n}\n', start) + 3
    return text[start:end]


@pytest.mark.parametrize('script', SCRIPTS)
@pytest.mark.parametrize('uid', [0, 1000])
@pytest.mark.parametrize('rc', [0, 20, 30])
def test_identity_arguments_output_and_status(script, uid, rc):
    harness = f'''
set -uo pipefail
IFS=$'\\n\\t'
id() {{ if [[ "$1" == '-u' ]]; then echo {uid}; else return 0; fi; }}
cli() {{ printf 'cli <%s> <%s>\\n' "$1" "$2"; return {rc}; }}
sudo() {{ printf 'sudo <%s> <%s> <%s>\\n' "$1" "$2" "$3"; shift 3; "$@"; }}
'''
    result = subprocess.run(
        ['bash', '-c', harness + helper(script) + '\ncli_as_service cli doctor "two words"'],
        capture_output=True, text=True,
    )
    assert result.returncode == rc
    assert result.stdout.endswith('cli <doctor> <two words>\n')
    assert ('sudo <-u> <khptz> <-->\n' in result.stdout) == (uid == 0)


@pytest.mark.parametrize('script', SCRIPTS)
def test_missing_service_user_never_falls_back_to_root(script):
    harness = '''
set -uo pipefail
id() { if [[ "$1" == '-u' ]]; then echo 0; else return 1; fi; }
sudo() { echo UNEXPECTED_SUDO; }
cli() { echo UNSAFE_ROOT_CLI; }
'''
    result = subprocess.run(
        ['bash', '-c', harness + helper(script) + '\ncli_as_service cli doctor'],
        capture_output=True, text=True,
    )
    assert result.returncode == 127
    assert result.stdout == ''
    assert 'refusing root CLI execution' in result.stderr


def test_deployment_both_execution_paths_use_service_wrapper():
    text = (ROOT / 'scripts' / SCRIPTS[0]).read_text()
    assert text.count('cli_as_service "${KHPTZ[@]}" "$@"') == 2
    assert '&& "${KHPTZ[@]}" "$@"' not in text


def test_acceptance_all_cli_calls_use_wrapper_including_optional_backup():
    text = (ROOT / 'scripts' / SCRIPTS[1]).read_text()
    assert 'cli_as_service khptz "${_cmd}"' in text
    assert 'cli_as_service khptz doctor 2>&1' in text
    assert 'cli_as_service khptz doctor --json' in text
    assert 'if cli_as_service khptz backup' in text
    assert '$(khptz ' not in text


def test_deployment_real_helpers_pass_through_service_wrapper():
    text = (ROOT / 'scripts' / SCRIPTS[0]).read_text()
    start = text.index('run_khptz() {')
    end = text.index('\nsection()', start)
    harness = '''
set -Eeuo pipefail
IFS=$'\\n\\t'
KHPTZ=(cli)
REPO_ROOT="$PWD"
id() { if [[ "$1" == '-u' ]]; then echo 0; else return 0; fi; }
sudo() { printf 'service-wrapper\n'; shift 3; "$@"; }
cli() { printf 'command:%s\n' "$1"; }
warn() { printf 'WARN:%s\n' "$*"; }
'''
    result = subprocess.run(
        ['bash', '-c', harness + helper(SCRIPTS[0]) + text[start:end]
         + '\nrun_khptz version\ncapture_khptz doctor'],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout == 'service-wrapper\ncommand:version\nservice-wrapper\ncommand:doctor\n'
