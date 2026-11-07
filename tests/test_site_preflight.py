import importlib.util
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/site_preflight.py'
spec = importlib.util.spec_from_file_location('site_preflight', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_inventory_missing_platform_data_never_claims_backup_or_hardware_pass():
    with patch.object(module, 'read', return_value='unknown'), \
         patch.object(module.shutil, 'which', return_value=None), \
         patch.object(module.importlib.util, 'find_spec', side_effect=ModuleNotFoundError):
        result = module.inventory()
    assert result['pi_model'] == 'unknown'
    assert result['disks'] == 'unknown'
    assert not any(result['modules'].values())
    assert result['backup'].startswith('MANUAL:')
    assert result['verdict'].startswith('INVENTORY ONLY:')


def test_only_external_command_is_read_only_lsblk():
    source = SCRIPT.read_text()
    assert source.count('subprocess.run(') == 1
    assert "['lsblk', '-b', '-o'," in source
    assert 'sudo' not in source
    assert 'write_text(' not in source


def test_exit_code_keeps_manual_gates_open(capsys):
    with patch.object(module, 'inventory', return_value={'verdict': 'INVENTORY ONLY'}):
        assert module.main() == 20
    assert 'INVENTORY ONLY' in capsys.readouterr().out
