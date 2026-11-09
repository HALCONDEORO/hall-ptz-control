#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# tests/test_run_khptz_fallback.py — _ensure_run_khptz behavioural contract
#
# The /run/khptz fallback runs when systemd-tmpfiles cannot create the
# provisioning channel directory. Mejora's review of #122 set the bar:
# never repair by inference (no chown/chmod of an existing path), accept
# only a real directory with exactly owner:root 0750, create restrictively
# and verify, and never promise the channel heals itself.

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "tests" / "installer" / "run_khptz_fallback_harness.sh"


def _run(tmp_path: Path, case: str) -> subprocess.CompletedProcess:
    work = tmp_path / case
    work.mkdir()
    return subprocess.run(
        ["bash", str(HARNESS), case, str(work)],
        capture_output=True, text=True,
        env={**os.environ, "INSTALL_CALLS": str(work / "install.calls")},
    )


def _func_rc(result: subprocess.CompletedProcess) -> int:
    for line in result.stdout.splitlines():
        if line.startswith("FUNC-RC="):
            return int(line.split("=", 1)[1])
    raise AssertionError(f"harness did not report FUNC-RC: {result.stdout}{result.stderr}")


class TestRunKhptzFallback:
    def test_absent_directory_is_created_restrictively_and_verified(self, tmp_path):
        result = _run(tmp_path, "absent")
        assert _func_rc(result) == 0, result.stdout + result.stderr
        assert "created directly with the same owner and mode" in result.stderr
        calls = (tmp_path / "absent" / "install.calls").read_text()
        assert "-m 0750" in calls

    def test_existing_correct_directory_is_used_untouched(self, tmp_path):
        result = _run(tmp_path, "correct")
        assert _func_rc(result) == 0, result.stdout + result.stderr
        assert "already exists with the expected owner and mode" in result.stdout
        # No repair by inference: install must never be called.
        assert not (tmp_path / "correct" / "install.calls").exists()

    def test_existing_0700_is_warned_and_left_alone(self, tmp_path):
        result = _run(tmp_path, "mode700")
        assert _func_rc(result) == 1
        assert "unexpected owner/group/mode" in result.stderr
        assert "not changing it by inference" in result.stderr
        # The directory keeps its 0700 mode: the fallback never re-modes.
        mode = oct((tmp_path / "mode700" / "run-khptz").stat().st_mode & 0o7777)[2:]
        assert mode == "700"
        assert not (tmp_path / "mode700" / "install.calls").exists()

    def test_existing_foreign_owner_is_warned_and_left_alone(self, tmp_path):
        result = _run(tmp_path, "other-owner")
        assert _func_rc(result) == 1
        assert "unexpected owner/group/mode" in result.stderr

    def test_symlink_is_refused_and_target_untouched(self, tmp_path):
        result = _run(tmp_path, "symlink")
        assert _func_rc(result) == 1
        assert "symlink" in result.stderr
        assert "refusing to use or modify it" in result.stderr
        assert (tmp_path / "symlink" / "real-target").is_dir()
        assert not (tmp_path / "symlink" / "install.calls").exists()

    def test_double_failure_warns_without_promising_healing(self, tmp_path):
        result = _run(tmp_path, "create-fails")
        assert _func_rc(result) == 1
        assert "Could not create" in result.stderr
        assert "unavailable now; verify after reboot" in result.stderr
        # Never claim the channel will work on its own later.
        assert "works after the next boot" not in result.stderr
