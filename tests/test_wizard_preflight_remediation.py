"""Blocked setup explains the action required to continue."""
import os
from pathlib import Path
import subprocess
import sys


def test_device_check_shows_blocking_remediation():
    script = r'''
from PyQt5.QtWidgets import QApplication
from PyQt5 import sip
from unittest.mock import patch
from application.preflight import PreflightCheck
from ui.setup_wizard import SetupWizard
app=QApplication([]);w=SetupWizard()
p=next(w.page(i) for i in w.pageIds() if type(w.page(i)).__name__=='DeviceCheckPage')
check=PreflightCheck('disk','Disk space',False,False,'Only 10 MB free','Free up space on the SD card before installing')
with patch('application.preflight.run_preflight',return_value=[check]):p.initializePage()
assert not p.isComplete()
assert check.detail in p._results.text()
assert check.remediation in p._results.text()
w.reject();sip.delete(w);app.processEvents()
'''
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
