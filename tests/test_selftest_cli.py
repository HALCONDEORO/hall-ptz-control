"""The installed self-test stays independent of pytest and real site paths."""
import json
from types import SimpleNamespace
from unittest.mock import patch


def test_selftest_command_is_registered():
    from runtime.cli import build_parser, _COMMANDS
    args = build_parser().parse_args(['selftest', '--json'])
    assert args.command == 'selftest'
    assert args.json
    assert 'selftest' in _COMMANDS


def test_selftest_uses_isolated_paths_and_reports_components():
    from runtime.selftest import run_selftest
    def run(command, **kwargs):
        env = kwargs['env']
        assert env['QT_QPA_PLATFORM'] == 'offscreen'
        assert 'khptz-selftest-' in env['KHPTZ_CONFIG_DIR']
        assert 'khptz-selftest-' in env['KHPTZ_APP_DIR']
        assert command[-1] in ('panel', 'visca')
        return SimpleNamespace(returncode=0, stdout=json.dumps([
            {'name': command[-1], 'passed': True, 'detail': 'checked'}]))
    with patch('runtime.selftest.subprocess.run', side_effect=run):
        checks = run_selftest()
    assert [check['name'] for check in checks] == ['visca', 'panel']


def test_selftest_failure_is_nonzero_and_does_not_claim_hardware(capsys):
    from runtime.selftest import cmd_selftest
    with patch('runtime.selftest.run_selftest', return_value=[{'name': 'panel', 'passed': False}]):
        assert cmd_selftest(SimpleNamespace(json=True)) == 1
    output = json.loads(capsys.readouterr().out)
    assert output['passed'] is False
    assert output['scope'] == 'offline regression, not hardware certification'
