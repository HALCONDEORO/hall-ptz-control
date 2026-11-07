"""Safety limits for the metadata-only PR labeling workflow."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow():
    return yaml.safe_load((ROOT / '.github/workflows/pr-labeler.yml').read_text())


def test_metadata_events_only_with_no_checkout_or_shell_execution():
    data = workflow()
    events = data.get('on', data.get(True))  # PyYAML YAML 1.1 parses on as True.
    assert events == {'pull_request_target': {'types': ['opened', 'synchronize', 'reopened']}}
    job = data['jobs']['label']
    assert job['timeout-minutes'] == 2
    assert len(job['steps']) == 1
    step = job['steps'][0]
    assert 'run' not in step
    assert step['uses'] == 'actions/labeler@b8dd2d9be0f68b860e7dae5dae7d772984eacd6d'
    assert step['with']['sync-labels'] is False


def test_only_required_token_permissions_and_no_new_secret():
    data = workflow()
    assert data['permissions'] == {'contents': 'read'}
    assert data['jobs']['label']['permissions'] == {'contents': 'read', 'pull-requests': 'write'}
    assert 'secrets.' not in str(data)
    assert data['concurrency']['cancel-in-progress'] is True


def test_label_config_uses_existing_documentation_label_only():
    data = yaml.safe_load((ROOT / '.github/labeler.yml').read_text())
    assert data == {'documentation': [{'changed-files': [{'any-glob-to-any-file': ['**/*.md', 'docs/**']}]}]}
