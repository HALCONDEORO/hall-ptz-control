"""Source files must not contain literal NUL bytes.

Bash silently ignores NUL bytes when reading a script, which turns
``tr -d '<NUL>'`` into ``tr -d ''`` (deletes nothing) and makes the file
"binary" for git and tooling. A literal NUL crept into
scripts/cleanup_legacy_rpi_autostart.sh once; keep it from coming back.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TEXT_GLOBS = ("*.sh", "*.py", "*.md", "*.yaml", "*.yml",
              "*.desktop", "*.service", "*.path", "*.ps1", "*.txt")


def test_no_nul_bytes_in_text_sources():
    offenders = []
    for pattern in TEXT_GLOBS:
        for path in REPO.rglob(pattern):
            parts = set(path.parts)
            if "__pycache__" in parts or ".git" in parts or ".venv" in parts:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in data:
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"NUL bytes found in: {offenders}"
