"""Safety documentation must distinguish API state from physical outcomes."""
from pathlib import Path


def test_operator_guide_does_not_certify_unobserved_hardware():
    text = (Path(__file__).resolve().parents[1] / 'docs/OPERATOR_GUIDE.md').read_text()
    assert 'API contracts, not a verified GUI checklist' in text
    assert 'does not confirm physical stopping' in text
    assert 'partial failure' in text.lower()
    assert 'session cleanup can succeed while a camera STOP fails' in text
    assert 'movement_state="unknown"' in text
    assert 'four runtime safety actions available' not in text
    assert 'leaves the system in the same known-good state' not in text


def test_documented_stop_all_route_matches_current_gui():
    root = Path(__file__).resolve().parents[1]
    guide = (root / 'docs/OPERATOR_GUIDE.md').read_text()
    readme = (root / 'README.md').read_text()
    assert 'red STOP ALL button below the camera' in guide
    assert 'without an active session or a connected camera' in guide
    assert 'Safety Reset is still a service contract' in guide
    assert 'red **STOP ALL** button below the camera controls' in readme
    assert 'Confirm the physical result' in readme
