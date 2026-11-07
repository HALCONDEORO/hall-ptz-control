"""Render dev launch assets without executing host installation operations."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32",
                                reason="requires native POSIX bash")


@pytest.fixture
def runtime_env(tmp_path):
    return dict(os.environ, APP_USER="desktop", INSTALL_DIR=str(tmp_path / "app"),
                CONFIG_DIR=str(tmp_path / "config"), DATA_DIR=str(tmp_path / "data"),
                LOG_DIR=str(tmp_path / "log"), BACKUP_DIR=str(tmp_path / "backup"))


def test_dev_unit_exports_config_directory(runtime_env, tmp_path):
    text = (ROOT / "runtime/installer/install.sh").read_text(encoding="utf-8")
    block = text.split('# Dev mode: patch paths and user')[1]
    block = 'sed \\\n' + block.split('\n    sed \\\n', 1)[1].split('\nfi', 1)[0]
    output = tmp_path / "dev.service"
    result = subprocess.run(["bash", "-eu", "-c", block], capture_output=True, text=True,
                            env=dict(runtime_env, SERVICE_FILE=str(output),
                                     SERVICE_TEMPLATE=str(ROOT / "runtime/systemd/khptz-control.service")))
    assert result.returncode == 0, result.stderr
    unit = output.read_text(encoding="utf-8")
    for key in ("CONFIG", "DATA", "LOG", "BACKUP"):
        assert f"Environment=KHPTZ_{key}_DIR={runtime_env[key + '_DIR']}" in unit


def test_dev_cli_uses_installed_runtime_directories(runtime_env, tmp_path):
    text = (ROOT / "runtime/installer/install.sh").read_text(encoding="utf-8")
    start = text.index('else\n    cat > "${KHPTZ_LAUNCHER}" <<LAUNCHER')
    block = text[start:].split('\nfi', 1)[0].removeprefix('else\n')
    launcher = tmp_path / "khptz"
    result = subprocess.run(["bash", "-eu", "-c", block], capture_output=True, text=True,
                            env=dict(runtime_env, KHPTZ_LAUNCHER=str(launcher)))
    assert result.returncode == 0, result.stderr
    Path(runtime_env['INSTALL_DIR']).mkdir()
    stubs = tmp_path / "bin"
    stubs.mkdir()
    python_stub = stubs / "python3"
    python_stub.write_text('#!/bin/bash\nenv | grep "^KHPTZ_"\n', encoding="utf-8")
    python_stub.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("KHPTZ_")}
    env['PATH'] = f"{stubs}:{env['PATH']}"
    result = subprocess.run(["bash", str(launcher), "status"], capture_output=True,
                            text=True, env=env)
    assert result.returncode == 0, result.stderr
    for key in ("CONFIG", "DATA", "LOG", "BACKUP"):
        assert f"KHPTZ_{key}_DIR={runtime_env[key + '_DIR']}" in result.stdout.splitlines()
