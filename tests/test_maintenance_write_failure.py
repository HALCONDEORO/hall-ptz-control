"""The CLI must not announce a maintenance record that could not be saved."""
from unittest.mock import patch

import pytest

from application.maintenance_service import MaintenanceService
from runtime.cli import main


def test_service_reports_write_failure(tmp_path):
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('occupied')
    with pytest.raises(OSError):
        MaintenanceService(data_dir=blocked).mark_complete()


def test_cli_returns_failure_without_success_message(tmp_path, capsys):
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('occupied')
    service = MaintenanceService(data_dir=blocked)
    with patch('application.maintenance_service.MaintenanceService', return_value=service):
        code = main(['maintenance', 'mark-complete'])
    output = capsys.readouterr()
    assert code == 1
    assert '[FAIL]' in output.err
    assert 'Maintenance recorded' not in output.out
    assert not (blocked / 'maintenance.json').exists()
