"""Execute the real pre-copy guard with inert managers and temporary sockets."""
import os
from pathlib import Path
import socket
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('state,stop_rc,after,show_rc,expected', [
    ('active', 0, 'inactive', 0, 0),
    ('activating', 0, 'inactive', 0, 0),
    ('inactive', 0, 'inactive', 0, 0),
    ('active', 7, 'active', 0, 1),
    ('active', 0, 'active', 0, 1),
    ('active', 0, 'inactive', 7, 1),
    ('', 0, '', 0, 1),
])
@pytest.mark.parametrize('mode', ['user', 'system'])
@pytest.mark.parametrize('discovery', ['listed', 'socket_only', 'error'])
@pytest.mark.parametrize('endpoint,unit_present', [('bus', True), ('systemd/private', True), ('bus', False), (None, False)])
def test_quiesce_before_copy(tmp_path, state, stop_rc, after, show_rc, expected, mode, endpoint, unit_present, discovery):
    source = (ROOT / 'runtime/installer/install.sh').read_text()
    # RED on old code: no guard runs, so all unsafe cases reach COPY.
    start = source.find('_stop_session_guis() {')
    helper = '' if start < 0 else source[start:source.index('\nif [[ "${DEV_MODE}" == "false" ]]; then\n    _stop_session_guis', start)]
    helper = helper.replace('[[ -f /etc/systemd/user/khptz-gui.service ]]', '[[ -f "$UNIT_FILE" ]]')
    unit = tmp_path / 'unit'
    if unit_present:
        unit.touch()
    runtime = tmp_path / 'run'
    (runtime / '1000').mkdir(parents=True)
    sock = socket.socket(socket.AF_UNIX)
    if endpoint:
        path = runtime / '1000' / endpoint
        path.parent.mkdir(exist_ok=True)
        sock.bind(str(path))
    else:
        expected = 1  # manager listed by systemd but no reachable endpoint
    if discovery == 'error':
        expected = 1
    elif discovery == 'socket_only' and endpoint is None:
        expected = 0  # neither source identifies a live manager
    try:
        script = '''set -euo pipefail
error() { echo "$*" >&2; exit 1; }
warn() { echo "$*" >&2; }
systemctl() {
    case "$DISCOVERY" in
        listed) echo 'user@1000.service loaded active running User Manager' ;;
        socket_only) return 0 ;;
        error) return 7 ;;
    esac
}
getent() { echo 'desktop:x:1000:1000::/home/desktop:/bin/bash'; }
sudo() {
    echo "$*" >> "$CALLS"
    case " $* " in
        *' stop '*) touch "$STOPPED"; return "$STOP_RC" ;;
        *' show '*)
            [[ "$SHOW_RC" == 0 ]] || return "$SHOW_RC"
            if [[ -f "$STOPPED" ]]; then echo "$AFTER"; else echo "$STATE"; fi ;;
        *) exit 99 ;;
    esac
}
'''+helper+'\n'+(' _stop_session_guis "$RUNTIME"\n' if helper else '')+'echo COPY\n'
        env = dict(os.environ, UNIT_FILE=str(unit), RUNTIME=str(runtime),
                   CALLS=str(tmp_path / 'calls'), STOPPED=str(tmp_path / 'stopped'),
                   STATE=state, STOP_RC=str(stop_rc), AFTER=after, SHOW_RC=str(show_rc),
                   GUI_MODE=mode, DISCOVERY=discovery)
        result = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True)
        assert result.returncode == expected, result.stdout + result.stderr
        assert ('COPY' in result.stdout) == (expected == 0)
        calls = (tmp_path / 'calls').read_text() if (tmp_path / 'calls').exists() else ''
        assert ' start ' not in calls and ' restart ' not in calls
        if endpoint and state == 'active' and expected == 0:
            assert 'stays stopped on success or failure' in result.stderr
    finally:
        sock.close()


def test_guard_precedes_copy_and_is_after_readonly_checks():
    source = (ROOT / 'runtime/installer/install.sh').read_text()
    assert source.index('    _stop_session_guis /run/user') < source.index('    rsync -a --delete')
    assert source.index('    _stop_session_guis /run/user') > source.index('# ── Copy application')
