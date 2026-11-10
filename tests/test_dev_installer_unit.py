"""Render the real dev-unit sed block without running the installer."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32",
                    reason="requires native POSIX bash and sed")
def test_dev_unit_can_read_home_checkout_and_write_runtime_data(tmp_path):
    installer = (ROOT / "runtime/installer/install.sh").read_text(encoding="utf-8")
    block = installer.split('# Dev mode: patch paths and user')[1]
    block = block.split('\n    sed \\\n', 1)[1]
    block = 'sed \\\n' + block.split('\nfi', 1)[0]
    output = tmp_path / "dev.service"
    result = subprocess.run(
        ["bash", "-eu", "-c", block], capture_output=True, text=True,
        env={
            "PATH": str(Path(shutil.which("sed")).parent),
            "APP_USER": "desktop",
            "INSTALL_DIR": "/home/desktop/khptz",
            "CONFIG_DIR": "/home/desktop/khptz",
            "DATA_DIR": "/home/desktop/.config/khptz",
            "LOG_DIR": "/var/log/khptz",
            "BACKUP_DIR": "/var/backups/khptz",
            "SERVICE_TEMPLATE": str(ROOT / "runtime/systemd/khptz-control.service"),
            "SERVICE_FILE": str(output),
        },
    )
    assert result.returncode == 0, result.stderr
    unit = output.read_text(encoding="utf-8")
    assert "WorkingDirectory=/home/desktop/khptz" in unit
    assert "ExecStart=/usr/bin/python3 /home/desktop/khptz/main.py" in unit
    assert "ProtectHome=read-only" in unit
    assert "ReadWritePaths=/home/desktop/.config/khptz /var/log/khptz /var/backups/khptz" in unit
    # Do not relax the product unit to make developer paths work.
    template = (ROOT / "runtime/systemd/khptz-control.service").read_text(encoding="utf-8")
    assert "ProtectHome=true" in template
