"""The visible percentage is unconfirmed until a current camera read arrives."""
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('response', ['silent_failure','current_same_value','current_new_value',
                                      'retired_endpoint','other_camera','new_intent','shutdown'])
def test_settled_zoom_stays_unconfirmed_until_current_readback(response):
    script=r'''
import sys
from unittest.mock import Mock,patch
from PyQt5.QtWidgets import QApplication,QWidget,QPushButton,QVBoxLayout
from ui.right_panel import RightPanel
from ui.camera_display_mixin import CameraDisplayMixin
app=QApplication([])
class Window(CameraDisplayMixin,QWidget):pass
w=Window();w.Cam1=QPushButton(w);w.Cam1.setCheckable(True);w.Cam1.setChecked(True)
w.Cam2=QPushButton(w);w.session_active=True;w._session=Mock(_session_generation=1)
w._shutting_down=False;w._zoom_intent_generation=1
port=Mock();port.display_generation.return_value=0;w._camera_port=port
panel=object.__new__(RightPanel);panel._mw=w;panel._container=QWidget();w._right_panel=panel
with patch('adapters.sim_mode.is_active',return_value=False):
    panel._add_ptz_block(QVBoxLayout(panel._container))
def feedback(pct):
    w._zoom_feedback=True
    try:w.ZoomSlider.setValue(pct)
    finally:w._zoom_feedback=False
w._set_zoom_feedback=feedback
feedback(77)
panel._zoom_dispatcher.settled.emit('cam1')
assert 'unconfirmed' in w.ZoomValueLabel.toolTip().lower()
assert panel._zoom_status_label.text()=='ZOOM ?'
assert '#AAAAAA' in w.ZoomValueLabel.styleSheet()
assert w.ZoomValueLabel.text()=='77%'
port.refresh_zoom_display.assert_called_once()
callback=port.refresh_zoom_display.call_args.args[1]
case=sys.argv[1]
if case=='retired_endpoint':port.display_generation.return_value=1
if case=='other_camera':w.Cam1.setChecked(False)
if case=='new_intent':w._zoom_intent_generation+=1
if case=='shutdown':w._shutting_down=True
if case!='silent_failure':callback(25 if case=='current_new_value' else 77)
app.processEvents();app.processEvents()
if case.startswith('current'):
    assert panel._zoom_status_label.text()=='ZOOM'
    assert not w.ZoomValueLabel.toolTip()
    assert '#666666' in w.ZoomValueLabel.styleSheet()
    assert w.ZoomValueLabel.text()==('25%' if case=='current_new_value' else '77%')
else:
    assert panel._zoom_status_label.text()=='ZOOM ?'
    assert w.ZoomValueLabel.text()=='77%'
# The indicator must not introduce polling or a second command.
assert port.refresh_zoom_display.call_count==1
port.zoom_absolute.assert_not_called()
w._zoom_timer.stop()
'''
    result=subprocess.run([sys.executable,'-c',script,response],
        cwd=Path(__file__).resolve().parents[1],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),
        capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
