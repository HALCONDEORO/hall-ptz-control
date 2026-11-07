"""Legacy secret migration uses the same atomic write contract as new secrets."""
from __future__ import annotations

import os
import stat

import pytest

from core import atomic_write
from runtime import secret_manager


@pytest.fixture
def paths(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy" / "password.enc"
    legacy.parent.mkdir()
    legacy.write_bytes(b"synthetic-migration-fixture")
    legacy.chmod(0o600)
    destination = tmp_path / "data" / "password.enc"
    destination.parent.mkdir()
    monkeypatch.setattr(secret_manager, "_CONFIG_DIR", destination.parent)
    monkeypatch.setattr(secret_manager, "_ENC_FILE", destination)
    return legacy, destination


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permission contract")
@pytest.mark.parametrize("mask", [0o000, 0o022])
@pytest.mark.parametrize("shared", [False, True])
def test_migration_stays_private_including_shared_data_dir(paths, mask, shared):
    legacy, destination = paths
    destination.parent.chmod(0o2770 if shared else 0o750)
    before = legacy.read_bytes()
    previous_mask = os.umask(mask)
    try:
        secret_manager._migrate_enc_file([legacy])
    finally:
        os.umask(previous_mask)
    assert destination.read_bytes() == before
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not legacy.exists()
    assert not destination.with_suffix(".enc.tmp").exists()


def test_migration_publishes_complete_private_file_before_removing_source(paths, monkeypatch):
    legacy, destination = paths
    replace = atomic_write.os.replace
    calls = []

    def checked_replace(source, target):
        assert legacy.exists()
        assert not destination.exists()
        assert source.read_bytes() == legacy.read_bytes()
        if os.name == "posix":
            assert stat.S_IMODE(source.stat().st_mode) == 0o600
        calls.append(target)
        replace(source, target)

    monkeypatch.setattr(atomic_write.os, "replace", checked_replace)
    secret_manager._migrate_enc_file([legacy])
    assert calls == [destination]
    assert destination.exists()
    assert not legacy.exists()


def test_migration_failure_preserves_source_and_removes_temporary_file(paths, monkeypatch):
    legacy, destination = paths
    before = legacy.read_bytes()

    def fail_replace(source, target):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(atomic_write.os, "replace", fail_replace)
    secret_manager._migrate_enc_file([legacy])
    assert legacy.read_bytes() == before
    assert not destination.exists()
    assert not destination.with_suffix(".enc.tmp").exists()
