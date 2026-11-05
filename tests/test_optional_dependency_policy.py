"""Keep the optional ATEM baseline explicit without downloading in CI."""
from pathlib import Path


def test_atem_requirement_is_exact_prerelease_baseline():
    root = Path(__file__).resolve().parents[1]
    requirements = [
        line.strip() for line in (root / "requirements-atem.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert requirements == ["PyATEMMax==1.0b9"]


def test_atem_distribution_gate_is_not_a_hardware_or_licence_approval():
    root = Path(__file__).resolve().parents[1]
    decision = (root / "docs/ATEM_DEPENDENCY_DECISION.md").read_text()
    assert "GNU GPL version 3" in decision
    assert "not an approval for customer distribution" in decision
    assert "hardware checks" in decision
