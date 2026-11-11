"""An unmeasured readiness check is a warning, never a passed check."""
from unittest.mock import patch

import pytest

from application import preflight


@pytest.mark.parametrize(
    'target,error,key',
    [
        ('shutil.disk_usage', OSError('unreadable working directory'), 'disk_space'),
        ('_rpi_advisory_checks', RuntimeError('probe unavailable'), 'rpi_advisories'),
    ],
)
def test_unavailable_probe_is_not_reported_as_passed(target, error, key):
    with patch.object(
        preflight.shutil if target.startswith('shutil.') else preflight,
        target.rsplit('.', 1)[-1],
        side_effect=error,
    ):
        checks = preflight.run_preflight(pyqt_available=True, python_version=(3, 11, 0))
    check = next(check for check in checks if check.key == key)
    assert not check.ok, 'An unavailable probe must not produce [OK] on Device check'
    assert check.warn_only
    assert not check.blocking
    assert check.remediation
    assert not preflight.has_blocking(checks)
