"""Hardware-free regression runner. No configured camera addresses are used."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def run_selftest():
    checks = []
    with TemporaryDirectory(prefix='khptz-selftest-') as root:
        env = os.environ.copy()
        env.update(QT_QPA_PLATFORM='offscreen', KHPTZ_PROFILE='production', HOME=root)
        for name in ('CONFIG', 'DATA', 'LOG', 'BACKUP', 'RUN', 'APP'):
            folder = Path(root) / name.lower()
            folder.mkdir()
            env[f'KHPTZ_{name}_DIR'] = str(folder)
        for component in ('visca', 'panel'):
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'runtime.selftest_support.runner', component],
                    env=env, capture_output=True, text=True, timeout=45,
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout).strip()[-2000:]
                    checks.append({'name': component, 'passed': False, 'detail': detail})
                    continue
                values = json.loads(result.stdout)
                if not isinstance(values, list) or not values:
                    raise ValueError('Self-test returned no checks')
                for check in values:
                    if (not isinstance(check, dict) or not isinstance(check.get('name'), str)
                            or not isinstance(check.get('passed'), bool)):
                        raise ValueError('Invalid self-test result')
                checks.extend(values)
            except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
                checks.append({'name': component, 'passed': False, 'detail': str(exc)})
    return checks


def cmd_selftest(args):
    checks = run_selftest()
    passed = all(check['passed'] for check in checks) and bool(checks)
    if getattr(args, 'json', False):
        print(json.dumps({'passed': passed, 'scope': 'offline regression, not hardware certification',
                          'checks': checks}, indent=2))
    else:
        print('KH PTZ offline regression self-test (no real camera commands)')
        for check in checks:
            print(f"{'PASS' if check['passed'] else 'FAIL'} {check['name']}: {check.get('detail', '')}")
        print('PASS' if passed else 'FAIL')
        print('This checks software regressions, not the connected cameras or their video.')
    return 0 if passed else 1
