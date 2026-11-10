"""Import-time safety of data_paths: a missing/uncreatable CONFIG_DIR must not
abort the interpreter.

data_paths is imported by main.py before logging or the crash reporter are
installed; an OSError from the import-time mkdir used to kill the whole
application with a bare traceback (a systemd restart loop with no log).
Subprocess-based: the import has to be exercised in a fresh interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_SNIPPET = (
    "import warnings\n"
    "warnings.simplefilter('ignore')\n"
    "import data_paths\n"
    "print('IMPORT-OK')\n"
)


def _run_import(env_data_dir: str) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    env["KHPTZ_DATA_DIR"] = env_data_dir
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-c", _SNIPPET],
        env=env, capture_output=True, text=True, timeout=60,
    )


def test_import_survives_uncreatable_data_dir(tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    # mkdir(parents=True) on <file>/child raises NotADirectoryError.
    result = _run_import(str(blocker / "child"))
    assert result.returncode == 0, result.stderr
    assert "IMPORT-OK" in result.stdout


def test_import_creates_data_dir_when_possible(tmp_path):
    target = tmp_path / "fresh" / "data"
    result = _run_import(str(target))
    assert result.returncode == 0, result.stderr
    assert "IMPORT-OK" in result.stdout
    assert target.is_dir()
