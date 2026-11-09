"""Collection-time stub leakage: the suite must be subset-independent.

test_splash_startup_sequence.py injects a bare `config` stub at module level;
its teardown_module restores sys.modules only after its TESTS run - far too
late to protect the COLLECTION of the next module in the same process.
test_dialogs_session_guard.py leaks `config` and `secret_manager` stubs the
same way. A full-suite run usually imported the real `config` earlier, so the
guards skipped stubbing and the leak stayed invisible; any subset (pytest -k,
one file, a chunk) could abort collection with:

    ImportError: cannot import name 'load_names_data' from 'config'
    (unknown location)

conftest.pytest_collectstart purges those leaked stubs between module
collections. These tests pin the purge list and prove the exact subset that
used to abort.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_purge_list_covers_config_and_secret_manager():
    conftest = (ROOT / "conftest.py").read_text()
    start = conftest.index("_LEAKY_STUB_MODULES = (")
    end = conftest.index("\n)", start)
    purge_list = conftest[start:end]
    assert '"config"' in purge_list
    assert '"secret_manager"' in purge_list


def test_subset_collection_splash_then_startup_does_not_abort():
    """The exact ordering that aborted: splash injects its `config` stub during
    collection, then startup_power_prompt imports ui.main_window, which does
    `from config import load_names_data`. --collect-only reaches that import
    without running any test."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "tests/test_splash_startup_sequence.py",
         "tests/test_startup_power_prompt.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
