"""The full apply plan remains reachable on the target touchscreen."""
import os
from pathlib import Path
import subprocess
import sys


def test_review_plan_scrolls_without_hiding_wizard_buttons():
    script = r'''
from PyQt5.QtWidgets import QApplication,QWizard,QScrollArea
from PyQt5 import sip
from ui.setup_wizard import SetupWizard
from application.provisioning_service import ProvisioningAnswers
app=QApplication([])
w=SetupWizard(answers=ProvisioningAnswers(entry_password='example-operator',admin_password='example-admin'))
pid=next(i for i in w.pageIds() if type(w.page(i)).__name__=='ReviewPage')
w.setStartId(pid);w.setFixedSize(800,480);w.show();app.processEvents();app.processEvents()
p=w.currentPage();areas=p.findChildren(QScrollArea)
assert len(areas)==1,'Review must expose a scrollable plan at800x480'
scroll=areas[0];bar=scroll.verticalScrollBar()
assert bar.maximum()>0
bar.setValue(bar.maximum());app.processEvents()
assert bar.value()==bar.maximum()
assert scroll.horizontalScrollBar().maximum()==0
assert w.button(QWizard.NextButton).isVisible()
assert w.button(QWizard.CancelButton).isVisible()
assert p._summary.height()>=p._summary.heightForWidth(p._summary.width())
w.reject();sip.delete(w);app.processEvents()
'''
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
