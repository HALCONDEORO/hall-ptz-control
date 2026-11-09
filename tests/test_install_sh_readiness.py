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


def _run(mode: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = None
    if env_extra:
        import os

        env = {**os.environ, **env_extra}
    return subprocess.run(
        ["bash", HARNESS, mode],
        capture_output=True, text=True, env=env,
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
        three known buckets (supported / not-validated / too-old)."""
        result = _run("real")
        assert "Python" in result.stdout
        assert any(
            marker in result.stdout for marker in ("3.9.x", "is NOT validated", "too old")
        )

    def test_wayland_session_is_a_blocking_fail(self):
        """Bookworm/Trixie default to Wayland, where the X11-only GUI never
        reaches the screen. The gate must FAIL and name the raspi-config
        switch, instead of letting the install proceed to a dead display."""
        result = _run("real", {"SESSION_TYPE": "wayland"})
        assert result.returncode == 1, result.stdout + result.stderr
        assert "[FAIL]" in result.stdout
        assert "Wayland" in result.stdout
        assert "raspi-config" in result.stdout

    def test_x11_session_passes_the_display_check(self):
        """An X11 session is the supported path: the gate reports PASS and the
        overall check still succeeds."""
        result = _run("real", {"SESSION_TYPE": "x11"})
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Display server: X11" in result.stdout

    def test_unknown_session_type_warns_but_does_not_block(self):
        """With no readable graphical session (e.g. installing over SSH before
        the first desktop login) the gate can only warn, never block."""
        result = _run("real", {"SESSION_TYPE": ""})
        assert result.returncode == 0, result.stdout + result.stderr
