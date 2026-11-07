"""A source override changes the checkout, never the installed GUI identity."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['user', 'system'])
@pytest.mark.parametrize('override', [False, True])
def test_source_override_preserves_recorded_gui_mode(tmp_path, mode, override):
    source = tmp_path / 'checkout'
    (source / '.git').mkdir(parents=True)
    installer = source / 'runtime/installer/install.sh'
    installer.parent.mkdir(parents=True)
    installer.write_text('# supports --gui-mode\n')
    installed = tmp_path / 'installed'
    installed.mkdir()
    state = tmp_path / 'install-state.env'
    state.write_text(f'KHPTZ_SOURCE_DIR="{source}"\nKHPTZ_GUI_MODE="{mode}"\n'
                     'KHPTZ_WIZARD_USER="desktop-user"\n'
                     'KHPTZ_INSTALLED_REF="new"\nKHPTZ_PREVIOUS_REF="old"\n')
    # Execute the complete production shell with only the fixed state path
    # redirected. Dry-run prevents any backup, checkout, install or restart.
    script = tmp_path / 'rollback.sh'
    text = (ROOT / 'runtime/installer/rollback.sh').read_text()
    script.write_text(text.replace('STATE_FILE="${CONFIG_DIR}/install-state.env"',
                                   f'STATE_FILE="{state}"'))
    bins = tmp_path / 'bin'
    bins.mkdir()
    for name, body in {
        'id': 'echo 0',
        'git': 'echo old',
        'systemctl': 'exit 1',
    }.items():
        target = bins / name
        target.write_text('#!/bin/sh\n' + body + '\n')
        target.chmod(0o755)
    args = ['bash', str(script), '--dry-run', '--dir', str(installed)]
    if override:
        args += ['--source', str(source)]
    result = subprocess.run(args, env={**os.environ, 'PATH': f'{bins}:{os.environ["PATH"]}'},
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '--wizard-user desktop-user --gui-mode ' + mode in result.stdout
    assert ('GUI runs as the desktop user' in result.stdout) == (mode == 'user')
