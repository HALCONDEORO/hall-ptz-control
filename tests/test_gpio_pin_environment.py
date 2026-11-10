"""Optional GPIO configuration must not prevent importing the application."""
import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('value,expected,warn', [('bad', 17, True), ('', 17, True), ('22', 22, False)])
def test_gpio_environment_parse_is_fail_safe(monkeypatch, caplog, value, expected, warn):
    monkeypatch.setenv('KHPTZ_GPIO_SCREEN_BTN_PIN', value)
    path = Path(__file__).resolve().parents[1] / 'adapters/gpio_monitor.py'
    spec = importlib.util.spec_from_file_location('gpio_environment_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.GPIO_SCREEN_BUTTON_PIN == expected
    assert ('KHPTZ_GPIO_SCREEN_BTN_PIN' in caplog.text) is warn
