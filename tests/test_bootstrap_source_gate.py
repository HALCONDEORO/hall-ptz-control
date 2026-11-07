"""Exercise source validation before desktop/installer host operations."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "install_khptz_rpi.sh"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32",
                                reason="requires native POSIX bash")


@pytest.mark.parametrize("identity,override,expected", [
    ("unknown", False, 30),
    ("unknown", True, 0),
    ("clean", False, 0),
    ("dirty", False, 30),
    ("dirty", True, 0),
])
def test_source_identity_gate(tmp_path, identity, override, expected):
    text = SCRIPT.read_text(encoding="utf-8")
    root_guard = 'if [[ "${EUID}" -ne 0 ]]; then'
    assert text.count(root_guard) == 1
    text = text.replace(root_guard, 'if false; then')
    boundary = '# ── Desktop user'
    assert text.count(boundary) == 1
    # The source gate runs verbatim; stop before user/session lookups.
    script = tmp_path / SCRIPT.name
    script.write_text(text.split(boundary)[0] + '\necho SOURCE_GATE_PASSED\n',
                      encoding="utf-8")
    installer = tmp_path / "runtime/installer/install.sh"
    installer.parent.mkdir(parents=True)
    installer.write_text("# inert placeholder\n", encoding="utf-8")
    stubs = tmp_path / "bin"
    stubs.mkdir()
    git = stubs / "git"
    git.write_text('''#!/bin/bash
if [[ "$TEST_IDENTITY" == unknown ]]; then exit 1; fi
case "$*" in
    *rev-parse*) echo abc123 ;;
    *status*) [[ "$TEST_IDENTITY" == dirty ]] && echo ' M synthetic.py'; exit 0 ;;
esac
''', encoding="utf-8")
    git.chmod(0o755)
    args = ["bash", str(script)] + (["--allow-dirty"] if override else [])
    result = subprocess.run(args, capture_output=True, text=True,
                            env=dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}",
                                     TEST_IDENTITY=identity))
    assert result.returncode == expected, result.stdout + result.stderr
    assert ("SOURCE_GATE_PASSED" in result.stdout) == (expected == 0)
    if identity == "unknown" and not override:
        assert "identify" in result.stderr
        assert "--allow-dirty" in result.stderr
