"""Product checks/dependencies must match the fixed system Python launcher."""
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'runtime/installer/install.sh').read_text()


def _section(start, end):
    return SOURCE[SOURCE.index(start):SOURCE.index(end)]


@pytest.mark.parametrize('dev,expected', [('true', 'python3'), ('false', '/usr/bin/python3')])
def test_selected_interpreter_matches_mode(dev, expected):
    selection = _section('# Product launchers use', 'SERVICE_NAME=')
    result = subprocess.run(['bash', '-c', f'DEV_MODE={dev}\n' + selection + '\necho "$PYTHON_BIN"'],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == expected


def test_product_dependency_checks_ignore_successful_path_python():
    functions = _section('require_pyqt5() {', '# ── Pre-flight checks')
    result = subprocess.run(['bash', '-c', '''
PYTHON_BIN=/usr/bin/python3
python3() { echo WRONG_INTERPRETER; return 0; }
function /usr/bin/python3() { return 1; }
error() { echo "$*"; exit 1; }
warn() { :; }
''' + functions + '\nrequire_pyqt5\necho ACCEPTED\n'], capture_output=True, text=True)
    assert result.returncode == 1, result.stdout
    assert 'PyQt5 not available' in result.stdout
    assert 'ACCEPTED' not in result.stdout


def test_product_atem_install_uses_the_same_python_module_pip():
    dependencies = _section('# ATEM support: install separately', '# ── Copy application files')
    result = subprocess.run(['bash', '-c', '''
DEV_MODE=false
INSTALL_ATEM=true
PYTHON_BIN=/usr/bin/python3
REPO_ROOT=/fake
info() { :; }
require_command() { :; }
pip3() { echo WRONG_PIP; return 99; }
function /usr/bin/python3() { printf '%s\\n' "$*"; }
''' + dependencies], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == '-m pip install --quiet -r /fake/requirements-atem.txt'


def test_version_and_readiness_use_selected_python():
    assert 'PYTHON_VERSION="$("${PYTHON_BIN}" -c' in SOURCE
    assert '_py_major="$("${PYTHON_BIN}" -c' in SOURCE
    assert '_py_minor="$("${PYTHON_BIN}" -c' in SOURCE
