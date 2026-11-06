"""The installer fixture tolerates transient downloads, not broken installs."""
from pathlib import Path


DOCKERFILE = Path(__file__).parent / "installer" / "Dockerfile.bullseye"


def test_snapshot_acquisition_retries_are_bounded():
    text = DOCKERFILE.read_text()
    assert 'Acquire::Retries "3";' in text
    assert 'Acquire::http::Timeout "30";' in text
    assert text.index("80snapshot-retries") < text.index("RUN apt-get update")


def test_snapshot_sources_stay_pinned_and_authenticated():
    text = DOCKERFILE.read_text()
    for suite in ("bullseye main", "bullseye-updates main", "bullseye-security main"):
        assert f"20260901T000000Z {suite}" in text
    assert "--allow-unauthenticated" not in text
    assert "trusted=yes" not in text


def test_failed_apt_install_is_not_suppressed():
    text = DOCKERFILE.read_text()
    block = text.split("RUN apt-get update", 1)[1].split("\n\n", 1)[0]
    assert "&& apt-get install -y --no-install-recommends" in block
    assert "||" not in block
    assert "--fix-missing" not in block
    assert "&& rm -rf /var/lib/apt/lists/*" in block
