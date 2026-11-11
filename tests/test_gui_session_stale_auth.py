"""An absent session XAUTHORITY must not inherit the user manager's old cookie."""
import json
import os
from pathlib import Path
import subprocess

import pytest

HELPER = Path(__file__).resolve().parents[1] / 'runtime/khptz-gui-session.sh'


@pytest.mark.parametrize('authority', [None, '/current/session/Xauthority'])
def test_new_session_drops_obsolete_authority(tmp_path, authority):
    state = tmp_path / 'manager.json'
    state.write_text(json.dumps({'XAUTHORITY': '/old/session/Xauthority'}))
    stub = tmp_path / 'systemctl'
    stub.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ['MANAGER_STATE'])
s = json.loads(p.read_text())
a = sys.argv[1:]
if a[0] == '--user':
    a = a[1:]
if a[0] == 'unset-environment':
    for k in a[1:]:
        s.pop(k, None)
elif a[0] == 'import-environment':
    for k in a[1:]:
        if k in os.environ:
            s[k] = os.environ[k]
elif a[0] == 'start':
    s['STARTED'] = True
p.write_text(json.dumps(s))
''')
    stub.chmod(0o755)
    logger = tmp_path / 'logger'
    logger.write_text('#!/bin/sh\nexit 0\n')
    logger.chmod(0o755)
    env = dict(os.environ, PATH=f'{tmp_path}:{os.environ["PATH"]}',
               MANAGER_STATE=str(state), DISPLAY=':0', XDG_SESSION_TYPE='x11')
    env.pop('XAUTHORITY', None)
    if authority is not None:
        env['XAUTHORITY'] = authority
    result = subprocess.run(['bash', str(HELPER)], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    final = json.loads(state.read_text())
    assert final['STARTED'] is True
    assert final.get('XAUTHORITY') == authority


def test_failed_unset_stops_before_import_or_start(tmp_path):
    calls = tmp_path / 'calls'
    stub = tmp_path / 'systemctl'
    stub.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
case "$*" in
    *unset-environment*) exit 7 ;;
esac
exit 0
''')
    stub.chmod(0o755)
    logger = tmp_path / 'logger'
    logger.write_text('#!/bin/sh\nexit 0\n')
    logger.chmod(0o755)
    env = dict(os.environ, PATH=f'{tmp_path}:{os.environ["PATH"]}',
               CALLS=str(calls), DISPLAY=':0', XDG_SESSION_TYPE='x11')
    env.pop('XAUTHORITY', None)
    result = subprocess.run(['bash', str(HELPER)], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    made = calls.read_text().splitlines()
    assert len(made) == 1
    assert made[0].startswith('--user unset-environment ')
    assert 'XAUTHORITY' in made[0]
    assert 'import-environment' not in calls.read_text()
    assert 'start' not in calls.read_text()
    assert 'Could not clear the previous session environment' in result.stdout
