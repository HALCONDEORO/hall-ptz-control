#!/usr/bin/env python3
"""Read-only on-site inventory. Never installs, repairs or approves deployment."""
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def read(path):
    try:
        return Path(path).read_text().replace('\x00', '').strip()
    except OSError:
        return 'unknown'


def inventory():
    result = {
        'pi_model': read('/proc/device-tree/model'),
        'os_release': read('/etc/os-release'),
        'architecture': platform.machine(),
        'python': platform.python_version(),
        'python_executable': sys.executable,
        'session_type': os.environ.get('XDG_SESSION_TYPE', 'unknown'),
        'display': os.environ.get('DISPLAY', 'unknown'),
        'commands': {name: bool(shutil.which(name)) for name in ('git', 'rsync', 'xhost', 'systemctl', 'gzip', 'cmp')},
        'modules': {},
        'disks': 'unknown',
        'backup': 'MANUAL: verified offline SD image or intact original SD required',
        'verdict': 'INVENTORY ONLY: not permission to install; backup and physical checks remain',
    }
    for name in ('yaml', 'PyQt5.QtCore', 'PyQt5.QtSvg'):
        try:
            result['modules'][name] = importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            result['modules'][name] = False
    if shutil.which('lsblk'):
        try:
            proc = subprocess.run(
                ['lsblk', '-b', '-o', 'NAME,PATH,SIZE,MODEL,TRAN,FSTYPE,MOUNTPOINTS'],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if proc.returncode == 0:
                result['disks'] = proc.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return result


def main():
    result = inventory()
    print(json.dumps(result, indent=2, ensure_ascii=True))
    # A successful inventory is not a successful deployment gate.
    return 20


if __name__ == '__main__':
    raise SystemExit(main())
