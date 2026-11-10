"""Keep the README's recovery entry points discoverable and safe."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_readme_has_operator_recovery_and_repository_map():
    text = (ROOT / 'README.md').read_text()
    for heading in ('## Camera operation and presets', '## Update and rollback',
                    '## Camera troubleshooting', '## Repository map'):
        assert heading in text
    for term in ('khptz verify-install', 'rollback.sh --dry-run',
                 '9041ff', 'a051ff', '9042ff', 'a052ff', 'chairman_presets.json'):
        assert term in text


def test_readme_separates_network_probes_from_passive_checks():
    text = (ROOT / 'README.md').read_text()
    assert 'do not run `khptz cameras` or `khptz doctor` alongside a live GUI' in text
    assert 'one controller process' in text
    assert 'not a physical motion confirmation' in text
    assert 'presets are stored in camera memory' in text


def test_readme_relative_links_and_images_resolve():
    text = (ROOT / 'README.md').read_text()
    links = re.findall(r'\]\(([^)]+)\)', text)
    for link in links:
        if '://' in link or link.startswith('#') or link.startswith('mailto:'):
            continue
        path = link.split('#', 1)[0]
        assert (ROOT / path).exists(), link


def test_readme_does_not_publish_site_network_details_or_unsafe_update_shortcuts():
    text = (ROOT / 'README.md').read_text()
    assert not re.search(r'\b(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)\d', text)
    assert 'git pull &&' not in text
    assert 'physical validation' in text
