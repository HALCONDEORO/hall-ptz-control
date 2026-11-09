#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# tests/test_install_sh_readiness.py — Executable coverage for install.sh --check (#888)
#
# `install.sh --check` is the readiness gate every deployment passes through,
# and the first physical install showed it is where real blockers surface — yet
# it had no executable coverage. A full write-side install needs a container
# (useradd, rsync, a live systemd); the readiness check is read-only, so
# tests/installer/readiness_harness.sh runs the REAL --check logic with stub
# implementations of the privileged/host commands it merely probes for.
#
# The harness is driven through bash. On Windows the `bash` pytest finds on PATH
# is typically WSL's, which cannot resolve a C:/ path, so these skip locally and
# run on Linux CI and on the Pi (same convention as test_rpi_bootstrap_script).

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = (REPO_ROOT / "tests" / "installer" / "readiness_harness.sh").as_posix()


def _run(mode: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", HARNESS, mode],
        capture_output=True, text=True,
    )


class TestHarnessFileContract:
    """These run everywhere — they only read the harness text."""

    def test_harness_exists(self):
        assert Path(HARNESS).is_file()

    def test_harness_never_mutates_the_real_tree(self):
        text = Path(HARNESS).read_text(encoding="utf-8")
        # The stripped mode must copy install.sh into a scratch root, never
        # delete templates from the checkout.
        assert "cp " in text
        assert "rm -rf" in text  # only ever the scratch/stub dirs, via trap
        assert 'trap ' in text

    def test_harness_only_prepends_stubs_for_one_run(self):
        text = Path(HARNESS).read_text(encoding="utf-8")
        assert 'PATH="${STUB_DIR}:${PATH}"' in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "the `bash` on PATH under Windows is typically WSL's, which cannot "
        "resolve a C:/ path; these run on Linux CI and on the Pi, where the "
        "installer actually ships"
    ),
)
class TestReadinessGate:
    def test_real_repo_passes_readiness(self):
        """A complete checkout has both required templates -> no blocking fail."""
        result = _run("real")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "=== KHPTZ Installer Readiness Check ===" in result.stdout
        assert "All required checks passed" in result.stdout

    def test_root_gate_is_satisfied_by_the_stub(self):
        """If the root stub failed, --check would abort before its own header."""
        result = _run("real")
        assert "must be run as root" not in result.stdout + result.stderr

    def test_missing_service_template_is_a_blocking_fail(self):
        """The systemd unit is required; without it the gate must FAIL and
        exit non-zero rather than let an unusable install proceed."""
        result = _run("stripped")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "[FAIL]" in result.stdout
        assert "service template missing" in result.stdout
        assert "blocking check(s) failed" in result.stdout

    def test_python_version_is_classified_not_ignored(self):
        """Whatever interpreter runs, the check must place it in one of the
        known buckets (supported legacy / supported installation target /
        not-a-target / too-old)."""
        result = _run("real")
        assert "Python" in result.stdout
        assert any(
            marker in result.stdout
            for marker in ("3.9.x", "3.11", "NOT a validated target", "too old")
        )

    def _run_mode(self, mode: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", HARNESS, mode, "--wizard-user", "tester"],
            capture_output=True, text=True,
        )

    def test_wayland_session_is_a_blocking_fail(self):
        """Both GUI launchers force QT_QPA_PLATFORM=xcb: an active Wayland
        desktop session (the Bookworm/Trixie default) must FAIL the gate with
        the raspi-config remedy, not pass and leave the screen dark on site."""
        result = self._run_mode("wayland")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "[FAIL]" in result.stdout
        assert "Wayland" in result.stdout
        assert "raspi-config" in result.stdout
        assert "blocking check(s) failed" in result.stdout

    def test_active_x11_beats_inactive_wayland(self):
        """A leftover Wayland session listed FIRST must not fail a machine
        whose active desktop is X11 (review #109: first-session selection)."""
        result = self._run_mode("mixed-x11-active")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "[PASS] Desktop session: X11" in result.stdout
        assert "[FAIL] Desktop session" not in result.stdout

    def test_active_wayland_beats_inactive_x11(self):
        """A leftover X11 session listed FIRST must not pass a machine whose
        active desktop is Wayland (review #109: the false-PASS direction)."""
        result = self._run_mode("mixed-wayland-active")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "[FAIL] Desktop session: Wayland" in result.stdout

    def test_uninspectable_session_warns_but_never_blocks(self):
        """No readable session (fresh boot, SSH, loginctl error): WARN with the
        raspi-config step, never a FAIL — and never a silent PASS on a machine
        that may default to Wayland (review #109)."""
        for mode in ("real", "loginctl-fails"):
            result = self._run_mode(mode)
            assert result.returncode == 0, result.stdout + result.stderr
            assert "[FAIL] Desktop session" not in result.stdout

    def test_loginctl_failure_warns_with_remedy(self):
        result = self._run_mode("loginctl-fails")
        assert "[WARN] No active desktop session to inspect" in result.stdout
        assert "raspi-config" in result.stdout
