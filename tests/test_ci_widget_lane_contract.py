"""New config page files cannot be silently left out of both CI lanes."""
from pathlib import Path


def test_config_pages_glob_and_main_smoke_run_unforked():
    workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/tests.yml').read_text()
    isolated, widget = workflow.split('- name: Run pytest (real widget trees, unforked)')
    assert '--ignore-glob=tests/test_config_pages_*.py' in isolated
    assert '--ignore=tests/test_main_window_smoke.py' in isolated
    assert 'tests/test_config_pages_*.py' in widget
    assert 'tests/test_config_pages_session_tab.py' not in widget
    assert 'tests/test_main_window_smoke.py' in widget
    assert '--forked' not in widget
