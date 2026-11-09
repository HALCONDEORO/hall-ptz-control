"""Optional ATEM prerequisites must fail before any install mutation."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('check', [True, False])
def test_atem_requires_pip_before_creating_user_or_directories(check):
    # All host-changing commands are inert sentinels. No root or Pi needed.
    script = r'''
command() {
    if [[ "$1" == '-v' && "$2" == 'pip3' ]]; then return 1; fi
    builtin command "$@"
}
id() { echo 0; }
function /usr/bin/python3() {
    [[ "$*" != *"import pip"* ]] || return 1
    case "$*" in
        *'sys.version_info.major)'*) echo 3 ;;
        *'sys.version_info.minor)'*) echo 9 ;;
        *'version_info.major}.'*) echo 3.9 ;;
    esac
}
git() { :; }
rsync() { echo MUTATION; return 99; }
systemctl() { echo MUTATION; return 99; }
useradd() { echo MUTATION; return 99; }
install() { echo MUTATION; return 99; }
chown() { echo MUTATION; return 99; }
set -- --atem ${2}
source "$INSTALLER_UNDER_TEST"
'''
    result = subprocess.run(
        ['bash', '-c', script, 'test', str(ROOT / 'runtime/installer/install.sh'),
         '--check' if check else ''], capture_output=True, text=True, env=dict(os.environ, INSTALLER_UNDER_TEST=str(ROOT / 'runtime/installer/install.sh')))
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert 'Required Python module not available: pip' in output, output
    assert 'sudo apt install -y python3-pip' in output, output
    assert 'MUTATION' not in output, output


def test_wrapper_passes_atem_to_readiness(tmp_path):
    source = (ROOT / 'install_khptz_rpi.sh').read_text()
    # Execute the real wrapper's check invocation, not a copy of its flags.
    start = source.index('_CHECK_ARGS=(--check --no-check-next-action --wizard-user')
    end = source.index('if [[ "${CHECK_ONLY}"', start)
    recorder = tmp_path / 'installer.sh'
    recorder.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$CAPTURE"\n')
    capture = tmp_path / 'args'
    env = dict(os.environ, CAPTURE=str(capture))
    result = subprocess.run(['bash', '-c', '''
DEV_MODE=false
GUI_MODE=system
WIZARD_USER=desktop
PASSTHROUGH=(--atem)
INSTALLER="$1"
fatal() { exit 99; }
''' + source[start:end], 'test', str(recorder)], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert capture.read_text().splitlines() == ['--check', '--no-check-next-action', '--wizard-user', 'desktop', '--gui-mode', 'system', '--atem']
