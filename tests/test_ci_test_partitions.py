"""Both CI lanes must cover every test file once, including future Qt tabs."""
import fnmatch
from pathlib import Path
import shlex
import yaml
import pytest

ROOT = Path(__file__).resolve().parents[1]


def partition_commands(workflow):
    data = yaml.safe_load((ROOT / '.github' / 'workflows' / workflow).read_text())
    commands = []
    for job in data['jobs'].values():
        for step in job.get('steps', []):
            command = shlex.split(step.get('run', ''))
            if command and command[0] in ('python', 'pytest') and ('pytest' in command or command[0] == 'pytest'):
                commands.append(command)
    return commands


def partition_files(commands, eligible):
    lanes = []
    for command in commands:
        ignored = [part.split('=', 1)[1] for part in command
                   if part.startswith(('--ignore=', '--ignore-glob='))]
        includes = [part for part in command if part.startswith('tests/')]
        lanes.append({path for path in eligible
                      if (not includes or any(fnmatch.fnmatchcase(path, pattern) for pattern in includes))
                      and not any(fnmatch.fnmatchcase(path, pattern) for pattern in ignored)})
    return lanes


@pytest.mark.parametrize('workflow', ['tests.yml', 'ci.yml'])
def test_ci_lanes_cover_all_test_files_exactly_once(workflow):
    eligible = {path.relative_to(ROOT).as_posix() for path in (ROOT / 'tests').rglob('test_*.py')}
    # Synthetic future config page catches an exclusion glob coupled to a stale
    # enumerated unforked list before the next tab is added or silently skipped.
    eligible.add('tests/test_config_pages_future_regression.py')
    commands = partition_commands(workflow)
    assert len(commands) == 2
    assert sum('--forked' in command for command in commands) == 1
    lanes = partition_files(commands, eligible)
    assert set.union(*lanes) == eligible, 'CI silently omits eligible test files'
    assert not set.intersection(*lanes), 'CI runs files in both isolation lanes'
    unforked = lanes[next(i for i, command in enumerate(commands) if '--forked' not in command)]
    assert all(path in unforked for path in eligible if path.startswith('tests/test_config_pages_'))
