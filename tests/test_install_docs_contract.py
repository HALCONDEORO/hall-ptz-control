"""Prevent documented install commands drifting away from the wrapper contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_guides_use_desktop_user_and_readiness_wrapper():
    for name in ("README.md", "docs/INSTALL_RPI.md", "docs/INSTALL_RPI_ES.md"):
        text = (ROOT / name).read_text()
        assert 'install_khptz_rpi.sh --wizard-user "$USER" --check' in text
        assert '--wizard-user khptz' not in text
        assert 'sudo ./runtime/installer/install.sh' not in text


def test_guides_do_not_claim_pi5_bullseye_or_silent_validator():
    baseline = (ROOT / "docs/RPI_RUNTIME_BASELINE.md").read_text()
    guide = (ROOT / "docs/INSTALL_RPI.md").read_text()
    assert "Requires Bookworm/Trixie, not Bullseye" in baseline
    assert "Tested target for MVP" not in baseline
    assert "creates a report directory" in guide
    assert "it changes\nnothing on the appliance" not in guide


def test_simulation_commands_use_existing_module_path():
    guide = (ROOT / "docs/INSTALL_RPI.md").read_text()
    assert "python3 sim_mode.py" not in guide
    assert (ROOT / "adapters/sim_mode.py").is_file()
