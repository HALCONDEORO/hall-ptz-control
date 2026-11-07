"""QtSvg is imported unconditionally by the GUI, not optional decoration."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_missing_qtsvg_fails_preflight_with_package_hint():
    source = (ROOT / 'runtime/installer/install.sh').read_text()
    start = source.index('require_pyqt5() {')
    end = source.index('\n}\n', start) + 3
    script = '''
PYTHON_BIN=python3
warn() { echo "WARN: $*"; }
error() { echo "ERROR: $*"; exit 1; }
python3() {
    [[ "$*" != *QtSvg* ]]
}
''' + source[start:end] + '\nrequire_pyqt5\necho PREFLIGHT_PASSED\n'
    result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert 'python3-pyqt5.qtsvg' in output, output
    assert 'PREFLIGHT_PASSED' not in output, output


def test_gui_really_has_hard_qtsvg_import():
    import ast
    tree = ast.parse((ROOT / 'ui/main_window.py').read_text())
    assert any(isinstance(node, ast.ImportFrom) and node.module == 'PyQt5.QtSvg'
               for node in tree.body)
