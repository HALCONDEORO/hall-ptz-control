"""An unresolved privileged apply must never be silently submitted twice."""
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('outcome', ['pending', 'timeout', 'unreadable', 'failure'])
def test_install_reentry_respects_known_outcome(outcome):
    script = '''
from PyQt5.QtWidgets import QApplication,QWizard
from application.provision_handoff import HandoffResult
from ui.setup_wizard import SetupWizard
from PyQt5 import sip
app=QApplication([])
class Handoff:
    poll_interval_s=60
    begins=0
    result=None
    def begin(self,answers):self.begins+=1
    def poll(self):return self.result
h=Handoff();w=SetupWizard(handoff=h)
p=next(w.page(i) for i in w.pageIds() if type(w.page(i)).__name__=='InstallingPage')
p.initializePage()
OUTCOME = %r
if OUTCOME=='timeout':h.result=HandoffResult(ok=False,timed_out=True)
if OUTCOME=='unreadable':h.result=HandoffResult(ok=False,error='unreadable result: malformed JSON',outcome_unknown=True)
if OUTCOME=='failure':h.result=HandoffResult(ok=False,error='validation rejected')
if h.result is not None:
    p._poll_once()
    assert p._timer.isActive() is (OUTCOME!='failure')
p.cleanupPage();p.initializePage()
assert h.begins==(2 if OUTCOME=='failure' else 1),h.begins
if OUTCOME!='failure':
    # A late definitive result remains recoverable for the same request.
    h.result=HandoffResult(ok=True);p._poll_once();assert p.isComplete()
    assert not p._timer.isActive()
w.reject();sip.delete(w);app.processEvents()
''' % outcome
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


def test_back_button_cannot_leave_pending_apply():
    script='''
from PyQt5.QtWidgets import QApplication,QWizard
from ui.setup_wizard import SetupWizard
from application.provisioning_service import ProvisioningAnswers
from PyQt5 import sip
app=QApplication([])
class Handoff:
    poll_interval_s=60
    def begin(self,answers):pass
    def poll(self):return None
w=SetupWizard(answers=ProvisioningAnswers(entry_password='operator-test',admin_password='admin-test'),handoff=Handoff())
w.setStartId(6);w.show();app.processEvents();w.next();app.processEvents()
assert type(w.currentPage()).__name__=='InstallingPage'
assert not w.button(QWizard.BackButton).isEnabled()
w.reject();sip.delete(w);app.processEvents()
'''
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


def test_unreadable_handoff_result_does_not_establish_failure(tmp_path):
    from application.provision_handoff import ProvisionHandoff
    request=tmp_path/'request.json';result=tmp_path/'result.json'
    result.write_text('{unfinished')
    observed=ProvisionHandoff(request,result).poll()
    assert observed is not None and not observed.ok
    assert observed.outcome_unknown is True
    assert "outcome is unknown" in observed.summary()
    assert "before another attempt" in observed.summary()


def test_definitive_handoff_failure_is_retryable(tmp_path):
    from application.provision_handoff import ProvisionHandoff
    result=tmp_path/'result.json';result.write_text('{"ok":false,"error":"invalid configuration"}')
    observed=ProvisionHandoff(tmp_path/'request.json',result).poll()
    assert observed is not None and not observed.ok
    assert observed.outcome_unknown is False
