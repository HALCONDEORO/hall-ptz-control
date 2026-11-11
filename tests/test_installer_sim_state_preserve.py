#!/usr/bin/env python3
"""Behavioural test: the deploy mirror must preserve simulation-mode state.

adapters/sim_mode.py keeps its on-disk footprint in the install dir
(/opt/khptz on a product install):

  - sim_ip_backup.json — marker for is_active() and only record of the
    operator's real camera/ATEM addresses;
  - PTZ1IP.txt / PTZ2IP.txt — the loopback values activate() writes.

install.sh mirrors the release into the install dir with
`rsync -a --delete`; rollback.sh re-deploys through install.sh.  Any of
those files not covered by RSYNC_EXCLUDES is silently erased by an
upgrade or rollback.  Losing the backup flips is_active() to False, and
the next boot hydrates the cameras from config.yaml — the real hardware
the operator had isolated — with the restore path gone.

This test runs a real rsync with the exclusion set parsed from
install.sh itself, so the mirror and the test cannot drift apart.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
INSTALL_SH = REPO_ROOT / "runtime" / "installer" / "install.sh"

SIM_STATE_FILES = ("sim_ip_backup.json", "PTZ1IP.txt", "PTZ2IP.txt")


def _rsync_excludes_from_install_sh() -> list[str]:
    """Parse the RSYNC_EXCLUDES array out of install.sh (order preserved)."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    # The closing paren sits alone on its line; inline `)` appear in comments.
    match = re.search(r"RSYNC_EXCLUDES=\((.*?)\n\)", text, re.DOTALL)
    assert match, "RSYNC_EXCLUDES array not found in install.sh"
    # Bash strips the single quotes when expanding "${RSYNC_EXCLUDES[@]}";
    # rsync must receive the bare patterns.
    return [
        f"--exclude={pattern}"
        for pattern in re.findall(r"--exclude='([^']+)'", match.group(1))
    ]


@pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync not available")
def test_deploy_mirror_preserves_simulation_state(tmp_path: Path):
    src = tmp_path / "release"
    dst = tmp_path / "installed"
    src.mkdir()
    dst.mkdir()

    # The release tree carries application code only.  Content length differs
    # and the installed copy is older, so `rsync -a` (size+mtime quick check)
    # cannot skip the refresh.
    (src / "main.py").write_text("# new release, with more code\n", encoding="utf-8")
    # The installed tree has the previous release, live simulation state and
    # a file from a newer release that --delete must still remove.
    (dst / "main.py").write_text("# old\n", encoding="utf-8")
    (dst / "sim_ip_backup.json").write_text(
        '{"PTZ1IP.txt": "192.168.1.50", "PTZ2IP.txt": "192.168.1.51"}\n',
        encoding="utf-8",
    )
    (dst / "PTZ1IP.txt").write_text("127.0.0.1", encoding="utf-8")
    (dst / "PTZ2IP.txt").write_text("127.0.0.2", encoding="utf-8")
    (dst / "newer_release_leftover.py").write_text("# stale\n", encoding="utf-8")

    excludes = _rsync_excludes_from_install_sh()
    subprocess.run(
        ["rsync", "-a", "--delete", *excludes, f"{src}/", f"{dst}/"],
        check=True,
    )

    for name in SIM_STATE_FILES:
        assert (dst / name).exists(), (
            f"deploy mirror deleted {name} — simulation state lost on upgrade"
        )
    assert "192.168.1.50" in (dst / "sim_ip_backup.json").read_text(
        encoding="utf-8"
    )
    # The mirror still does its job: code is refreshed and stale files go.
    assert (dst / "main.py").read_text(encoding="utf-8") == (
        "# new release, with more code\n"
    )
    assert not (dst / "newer_release_leftover.py").exists()
