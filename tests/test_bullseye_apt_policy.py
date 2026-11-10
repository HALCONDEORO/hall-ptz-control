"""Exercise acquisition control flow without root, network or package installs."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).parent / "installer"
SCRIPT = ROOT / "acquire_snapshot_packages.sh"
DOCKERFILE = ROOT / "Dockerfile.bullseye"


def test_snapshot_policy_remains_pinned_and_signed():
    text = DOCKERFILE.read_text()
    for suite in ("bullseye main", "bullseye-updates main", "bullseye-security main"):
        assert f"20260901T000000Z {suite}" in text
    assert 'Acquire::Retries "3";' in text
    assert 'Acquire::http::Timeout "30";' in text
    assert "APT::Update::Error-Mode=any update" in text
    assert text.index("Error-Mode=any update") < text.index("RUN bash /usr/local/libexec/khptz-acquire-snapshot")
    for forbidden in ("--allow-unauthenticated", "trusted=yes", "--fix-missing", "ADD --checksum"):
        assert forbidden not in text


def run_fixture(tmp_path, mode="fallback", digest=None, uri=None, size=None):
    cache = tmp_path / "cache"
    cache.mkdir()
    commands = tmp_path / "bin"
    commands.mkdir()
    payload = tmp_path / "payload"
    payload.write_bytes(b"test archive, never installed")
    digest = digest or "SHA256:" + hashlib.sha256(payload.read_bytes()).hexdigest()
    uri = uri or "http://snapshot.debian.org/archive/debian/20260901T000000Z/pool/main/t/test/test_1_amd64.deb"
    plan = tmp_path / "plan"
    plan.write_text(f"summary\n'{uri}' test_1_amd64.deb {payload.stat().st_size if size is None else size} {digest}\n")
    log = tmp_path / "log"
    for name, text in {
        "apt-get": '''#!/bin/bash
printf 'apt %s\\n' "$*" >> "$TEST_LOG"
if [[ $* == *--print-uris* ]]; then cat "$TEST_PLAN"; exit 0; fi
[[ $* == *--no-download* ]] && [[ -f "$TEST_CACHE/test_1_amd64.deb" ]]
''',
        "helper": '''#!/bin/bash
printf 'helper %s\\n' "$*" >> "$TEST_LOG"
[[ $TEST_MODE == unavailable ]] && exit 1
[[ $TEST_MODE == fallback && $* != *snapshot-cloudflare* ]] && exit 1
cp "$TEST_PAYLOAD" "${@: -2:1}"
''',
        "sleep": '#!/bin/bash\nprintf "sleep %s\\n" "$*" >> "$TEST_LOG"\n',
    }.items():
        path = commands / name
        path.write_text(text)
        path.chmod(0o755)
    # Only external command locations/cache are redirected; execute real script logic.
    script = tmp_path / "acquire.sh"
    script.write_text(SCRIPT.read_text().replace("/var/cache/apt/archives", str(cache)).replace("/usr/lib/apt/apt-helper", str(commands / "helper")))
    env = dict(os.environ, PATH=str(commands) + ":" + os.environ["PATH"], TEST_MODE=mode,
               TEST_LOG=str(log), TEST_PLAN=str(plan), TEST_PAYLOAD=str(payload), TEST_CACHE=str(cache))
    result = subprocess.run(["bash", str(script), "test"], env=env, capture_output=True, text=True, timeout=5)
    return result, log.read_text(), cache


def test_primary_failure_uses_mirror_and_installs_only_verified_cache(tmp_path):
    result, log, cache = run_fixture(tmp_path)
    assert result.returncode == 0, result.stderr
    assert log.count("helper ") == 2
    assert "snapshot-cloudflare.debian.org/archive/debian/20260901T000000Z" in log
    assert "Acquire::ForceHash=SHA256" in log
    assert "--no-download" in log
    assert (cache / "test_1_amd64.deb").exists()
    assert not (cache / "khptz-acquire.partial").exists()


def test_persistent_outage_is_bounded_and_never_installs(tmp_path):
    result, log, cache = run_fixture(tmp_path, mode="unavailable")
    assert result.returncode != 0
    assert log.count("helper ") == 6
    assert log.count("sleep ") == 2
    assert "--no-download" not in log
    assert not (cache / "test_1_amd64.deb").exists()


def test_tampered_package_fails_closed_even_if_downloader_claims_success(tmp_path):
    result, log, cache = run_fixture(tmp_path, mode="primary", digest="SHA256:" + "0" * 64)
    assert result.returncode != 0
    assert "--no-download" not in log
    assert not (cache / "test_1_amd64.deb").exists()


@pytest.mark.parametrize("digest,uri", [
    ("MD5Sum:" + "0" * 32, None),
    (None, "http://example.invalid/test.deb"),
    (None, "http://snapshot.debian.org/archive/debian/20260902T000000Z/pool/test.deb"),
])
def test_untrusted_or_unpinned_plan_fails_before_download(tmp_path, digest, uri):
    result, log, _ = run_fixture(tmp_path, digest=digest, uri=uri)
    assert result.returncode != 0
    assert "helper " not in log
    assert "--no-download" not in log


def test_wrong_size_fails_closed_before_cache_publish(tmp_path):
    result, log, cache = run_fixture(tmp_path, mode="primary", size=999)
    assert result.returncode != 0
    assert "--no-download" not in log
    assert not (cache / "test_1_amd64.deb").exists()


def test_primary_success_does_not_contact_mirror(tmp_path):
    result, log, _ = run_fixture(tmp_path, mode="primary")
    assert result.returncode == 0, result.stderr
    assert log.count("helper ") == 1
    assert "snapshot-cloudflare" not in log
    assert "sleep " not in log
