"""Use exactly the same scenarios as the installed self-test, without drift."""
import pytest
from runtime.selftest_support.visca import (
    SCENARIOS, check_worker_camera, check_adapter_delayed_recall,
)


@pytest.mark.parametrize('replies,close,expected', SCENARIOS)
def test_scripted_worker_camera(replies, close, expected):
    check_worker_camera(replies, close, expected)


def test_adapter_delayed_recall_uses_same_persistent_session():
    check_adapter_delayed_recall()
