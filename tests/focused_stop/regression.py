"""Offline, stdlib-only STOP regression runner; --tree selects untouched baseline.

Real bus/controller/adapter and worker queue/confirmation methods. Qt signals
are stubbed; workers have no transport consumer and never construct sockets.
"""
import argparse
from pathlib import Path
import os
import queue
import sys
sys.dont_write_bytecode = True
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

parser = argparse.ArgumentParser()
parser.add_argument('--tree', type=Path, default=Path(__file__).resolve().parents[2])
args, unittest_args = parser.parse_known_args()
sys.path.insert(0, str(args.tree.resolve()))
_sandbox = tempfile.TemporaryDirectory(prefix='kh-stop-tests-')
os.environ['KHPTZ_DATA_DIR'] = _sandbox.name
os.environ['KHPTZ_CONFIG_DIR'] = _sandbox.name

class Signal:
    def emit(self, *args):
        pass

qt = types.ModuleType('PyQt5.QtCore')
qt.QObject = type('QObject', (), {})
qt.pyqtSignal = lambda *args: Signal()
package = types.ModuleType('PyQt5')
package.QtCore = qt
sys.modules['PyQt5'] = package
sys.modules['PyQt5.QtCore'] = qt

from core.events import AsyncEventBus, EventType
from core.controller import Controller
from core.state import SystemState
from adapters.visca_camera_adapter import ViscaCameraAdapter
from application.runtime_safety_service import RuntimeSafetyService
from ptz.visca.worker import CameraWorker

TIMEOUT = 2

def reached(event):
    if not event.wait(TIMEOUT):
        raise AssertionError('synchronization point not reached')

class QueueWorker(CameraWorker):
    """Use production admissions without starting a transport/socket thread."""
    def __init__(self, ip):
        self.ip = ip
        self._queue = queue.Queue(maxsize=20)
        self._shutdown = threading.Event()
        self._interrupt = threading.Event()
        self.entered = threading.Event()
        self.stopped = threading.Event()
        self.hold_recall = False
        self.inflight = None
        self.history = []

    def send(self, cmd):
        ok = super().send(cmd)
        if ok:
            self.history.append(cmd.payload)
            if cmd.payload[1:5] == bytes.fromhex('01043f02'):
                if self.hold_recall:
                    self.inflight = self._queue.get_nowait()
                    self.entered.set()
                else:
                    cmd.on_success()
            elif cmd.fast_connect:
                cmd.on_success()
        return ok

    def send_priority(self, cmd, **kwargs):
        return self._send_priority_admitted(cmd, **kwargs)

    def _send_priority_admitted(self, cmd, **kwargs):
        admitted = getattr(super(), '_send_priority_admitted', None)
        ok = (admitted(cmd, **kwargs) if admitted is not None else
              super().send_priority(cmd))
        if self._is_stop_payload(cmd.payload):
            self.stopped.set()
        elif ok:
            self.history.append(cmd.payload)
        return ok

    def _send_stop_batch_admitted(self, commands, **kwargs):
        ok = super()._send_stop_batch_admitted(commands, **kwargs)
        if ok:
            self.stopped.set()
        return ok

    def finish_late(self):
        self.hold_recall = False
        if self.inflight is not None:
            self.inflight.on_success()
            self.inflight = None

    def pending(self):
        with self._queue.mutex:
            return [cmd.payload for cmd in self._queue.queue if cmd is not None]

class Manager:
    def __init__(self):
        self.workers = {ip: QueueWorker(ip) for ip in ('synthetic-a', 'synthetic-b')}
        self.invalidations = []
        self.pause_thread = None
        self.before_admission = threading.Event()
        self.resume = threading.Event()

    def worker(self, ip):
        if threading.current_thread() is self.pause_thread:
            self.pause_thread = None
            self.before_admission.set()
            reached(self.resume)
        return self.workers[ip]

    def invalidate_zoom(self, ip):
        self.invalidations.append(ip)

class Rig:
    def __init__(self, aliases=False, controller_class=Controller):
        self.bus = AsyncEventBus()
        self.state = SystemState()
        self.state.session.active = True
        self.manager = Manager()
        self.port = ViscaCameraAdapter(self.manager, cam_configs={
            1: ('synthetic-a', '81'),
            2: ('synthetic-a' if aliases else 'synthetic-b', '82'),
        })
        self.presets = Mock()
        self.presets.get_preset_for_name.return_value = 7
        self.controller = controller_class(self.state, self.bus, self.presets, Mock(), self.port)
        self.a = self.manager.workers['synthetic-a']
        self.b = self.manager.workers['synthetic-b']
        self.bus.start()

    def flush(self):
        done = threading.Event()
        self.bus.subscribe(EventType.CONNECTION_CHANGED, lambda event: done.set())
        self.bus.emit(EventType.CONNECTION_CHANGED)
        reached(done)

    def close(self):
        self.manager.resume.set()
        for worker in self.manager.workers.values():
            worker.finish_late()
        self.bus.stop()

    def recall(self, **payload):
        self.a.hold_recall = True
        self.bus.emit(EventType.SEAT_SELECTED, camera=1, preset=4, **payload)
        reached(self.a.entered)

class StopRegression(unittest.TestCase):
    def setUp(self):
        self.no_network = patch('socket.socket', side_effect=AssertionError('network forbidden'))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def rig(self, **kwargs):
        rig = Rig(**kwargs)
        self.addCleanup(rig.close)
        return rig

    def test_reproducer_stop_other_endpoint_before_recall_release(self):
        r = self.rig()
        r.recall()
        r.bus.emit(EventType.CAMERA_STOP, camera=2)
        reached(r.b.stopped)
        self.assertIsNotNone(r.a.inflight)

    def test_queued_intents_cancel_same_endpoint_other_survives_fresh_allowed(self):
        r = self.rig()
        r.recall()
        for event, payload in (
            (EventType.CAMERA_MOVE, dict(pan_speed=3, tilt_speed=2)),
            (EventType.CAMERA_ZOOM, dict(speed=3)),
            (EventType.CAMERA_HOME, {}),
            (EventType.SEAT_SELECTED, dict(seat_number=6)),
            (EventType.CHAIRMAN_ASSIGNED, dict(name='synthetic-chair')),
        ):
            r.bus.emit(event, camera=1, **payload)
        r.bus.emit(EventType.CAMERA_MOVE, camera=2, pan_speed=4, tilt_speed=0)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.a.finish_late()
        r.flush()
        self.assertEqual(len(r.a.history), 1, 'stale bus movement admitted after STOP')
        self.assertEqual(len(r.b.history), 1, 'other endpoint work was canceled')
        r.bus.emit(EventType.CAMERA_MOVE, camera=1, pan_speed=5, tilt_speed=0)
        r.flush()
        self.assertEqual(len(r.a.history), 2)
        self.assertEqual(r.state.cam1.pan_speed, 5)

    def test_dequeued_before_admission_is_canceled(self):
        paused, resume = threading.Event(), threading.Event()
        class PausedController(Controller):
            def _on_camera_move(self, event):
                paused.set()
                reached(resume)
                return super()._on_camera_move(event)
        r = self.rig(controller_class=PausedController)
        self.addCleanup(resume.set)
        r.bus.emit(EventType.CAMERA_MOVE, camera=1, pan_speed=3, tilt_speed=0)
        reached(paused)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        resume.set()
        r.flush()
        self.assertEqual(r.a.history, [])

    def test_pause_inside_adapter_before_queue_admission(self):
        r = self.rig()
        r.manager.pause_thread = r.bus._worker
        r.bus.emit(EventType.CAMERA_MOVE, camera=1, pan_speed=3, tilt_speed=0)
        reached(r.manager.before_admission)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.manager.resume.set()
        r.flush()
        self.assertEqual(r.a.history, [])
        self.assertEqual(r.state.cam1.pan_speed, 0)

    def test_late_success_does_not_restore_state(self):
        r = self.rig()
        r.state.cam1.active_preset = 2
        r.recall()
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.a.finish_late()
        r.flush()
        self.assertEqual(r.state.cam1.active_preset, 2)
        self.assertEqual(r.manager.invalidations, [])

    def test_active_default_and_endpoint_aliases(self):
        r = self.rig(aliases=True)
        r.recall()
        r.state.active_camera = 2
        r.bus.emit(EventType.SEAT_SELECTED, seat_number=6)
        r.bus.emit(EventType.CAMERA_MOVE, camera=2, pan_speed=3, tilt_speed=0)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.a.finish_late()
        r.flush()
        self.assertEqual(len(r.a.history), 1)
        self.assertIsNone(r.state.cam2.active_preset)
        self.assertEqual(r.state.cam2.pan_speed, 0)

    def test_no_session_and_repeated_stop(self):
        r = self.rig()
        r.state.session.active = False
        for _ in range(30):
            r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.flush()
        pending = r.a.pending()
        self.assertEqual(len(pending), 2)
        self.assertTrue(all(r.a._is_stop_payload(p) for p in pending))

    def test_runtime_safety_retires_bus_work(self):
        r = self.rig()
        r.recall()
        r.bus.emit(EventType.CAMERA_HOME, camera=1)
        self.assertTrue(RuntimeSafetyService(r.port).stop_camera('cam1').ok)
        r.a.finish_late()
        r.flush()
        self.assertEqual(len(r.a.history), 1)

    def test_inflight_priority_home_never_replays_after_stop(self):
        from ptz.visca.worker import ViscaCommand
        worker = CameraWorker.__new__(CameraWorker)
        worker.ip = '192.0.2.1'
        worker._queue = queue.Queue(maxsize=20)
        worker._shutdown = threading.Event()
        worker._interrupt = threading.Event()
        worker._lock = threading.Lock()
        worker._sock = Mock()
        worker._set_connected = Mock()
        worker._close_socket = Mock()
        worker._consecutive_no_response = 0
        sent = []
        worker._sock.sendall.side_effect = lambda payload: sent.append(payload)
        failed = Mock()
        home = ViscaCommand(camera=1, payload=bytes.fromhex('81010604ff'),
                            priority=True, on_failure=failed)
        stop = ViscaCommand(camera=1, payload=bytes.fromhex('8101060100000303ff'))
        def read(sock):
            if len(sent) == 1:
                worker.send_priority(stop)
            else:
                worker._shutdown.set()
                worker._queue.put(None)
            return bytes.fromhex('9051ff')
        worker._read_visca_response = read
        worker._queue.put(home)
        worker._run()
        self.assertEqual(sent, [home.payload, stop.payload])
        self.assertTrue(home.cancelled.is_set())
        failed.assert_called_once()
        self.assertNotIn(home.payload, [c.payload for c in worker._queue.queue
                                      if c is not None])

    def test_worker_pending_commands_are_drained(self):
        r = self.rig()
        r.port.move('cam1', 3, 0)
        r.port.zoom('cam1', 3)
        r.port.home('cam1')
        r.port.move('cam2', 4, 0)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.flush()
        self.assertEqual(len(r.a.pending()), 2)
        self.assertTrue(all(r.a._is_stop_payload(p) for p in r.a.pending()))
        self.assertEqual(len(r.b.pending()), 1)

    def test_runtime_stop_cancels_legacy_chairman_and_alias_queued_intents(self):
        r = self.rig(aliases=True)
        r.recall()
        r.state.active_camera = 2
        r.bus.emit(EventType.SEAT_SELECTED, seat_number=8)
        r.bus.emit(EventType.CHAIRMAN_ASSIGNED, name='synthetic-chair')
        r.bus.emit(EventType.CAMERA_MOVE, camera=2, pan_speed=3, tilt_speed=0)
        r.bus.emit(EventType.CAMERA_ZOOM, camera=2, speed=3)
        r.bus.emit(EventType.CAMERA_HOME, camera=2)
        self.assertTrue(RuntimeSafetyService(r.port).stop_camera('cam1').ok)
        r.a.finish_late()
        r.flush()
        self.assertEqual(len(r.a.history), 1, 'queued legacy/alias work survived STOP')
        self.assertIsNone(r.state.cam1.active_preset)
        self.assertIsNone(r.state.cam2.active_preset)

    def test_requeued_stop_precedes_fresh_move(self):
        from ptz.visca.worker import ViscaCommand
        worker = QueueWorker('synthetic-a')
        pt = ViscaCommand(camera=1, payload=bytes.fromhex('8101060100000303ff'))
        zoom = ViscaCommand(camera=1, payload=bytes.fromhex('8101040700ff'))
        move = ViscaCommand(camera=1, payload=bytes.fromhex('8101060105000203ff'))
        worker.send_priority(pt)
        inflight = worker._queue.get_nowait()
        worker.send_priority(zoom)
        worker.send(move)
        worker._requeue(inflight)
        self.assertEqual(worker.pending(), [zoom.payload, pt.payload, move.payload])

    def test_failed_runtime_stop_does_not_strand_future_motion(self):
        r = self.rig()
        with patch.object(r.manager, 'worker', side_effect=RuntimeError('synthetic failure')):
            self.assertFalse(RuntimeSafetyService(r.port).stop_camera('cam1').ok)
        finished = threading.Event()
        def move():
            r.port.move('cam1', 3, 0)
            finished.set()
        thread = threading.Thread(target=move, daemon=True)
        thread.start()
        # Cleanup can release the synthetic failure barrier even on a bad patch.
        fence = getattr(r.port, '_motion_admission', None)
        if fence is not None:
            self.addCleanup(fence.capture('cam1').ready.set)
        reached(finished)
        thread.join(TIMEOUT)

    def test_fresh_move_state_survives_delayed_stop_handler_return(self):
        r = self.rig()
        admitted, resume = threading.Event(), threading.Event()
        original = r.port.stop_move
        def delayed(camera_id):
            result = original(camera_id)
            admitted.set()
            reached(resume)
            return result
        self.addCleanup(resume.set)
        r.port.stop_move = delayed
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(admitted)
        r.bus.emit(EventType.CAMERA_MOVE, camera=1, pan_speed=5, tilt_speed=0)
        r.flush()
        self.assertEqual(r.state.cam1.pan_speed, 5)
        stopped = threading.Event()
        r.bus.subscribe(EventType.CAMERA_STOP, lambda event: stopped.set())
        resume.set()
        reached(stopped)
        self.assertEqual(r.state.cam1.pan_speed, 5)

    def test_emits_do_not_wait_for_slow_emergency_worker_lookup(self):
        r = self.rig()
        entered, resume, emitted = threading.Event(), threading.Event(), threading.Event()
        original = r.manager.worker
        def lookup(ip):
            if threading.current_thread().name == 'AsyncEventBus-STOP':
                entered.set()
                reached(resume)
            return original(ip)
        self.addCleanup(resume.set)
        r.manager.worker = lookup
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(entered)
        def emit():
            r.bus.emit(EventType.CAMERA_MOVE, camera=1, pan_speed=3, tilt_speed=0)
            r.bus.emit(EventType.CAMERA_STOP, camera=2)
            emitted.set()
        thread = threading.Thread(target=emit, daemon=True)
        thread.start()
        reached(emitted)
        resume.set()
        reached(r.a.stopped)
        reached(r.b.stopped)
        thread.join(TIMEOUT)
        r.flush()
        self.assertEqual(len(r.a.history), 1)
        self.assertEqual(r.state.cam1.pan_speed, 3)

    def test_worker_queued_confirmed_recall_canceled_without_timeout(self):
        r = self.rig()
        queued, finished = threading.Event(), threading.Event()
        result = []
        def send(cmd):
            ok = CameraWorker.send(r.a, cmd)
            queued.set()
            return ok
        r.a.send = send
        def recall():
            result.append(r.port.recall_preset('cam1', 4).ok)
            finished.set()
        thread = threading.Thread(target=recall, daemon=True)
        thread.start()
        reached(queued)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(finished)
        thread.join(TIMEOUT)
        self.assertEqual(result, [False])
        self.assertTrue(all(r.a._is_stop_payload(p) for p in r.a.pending()))

    def test_late_recall_invalidation_after_state_commit_is_suppressed(self):
        r = self.rig()
        entered, resume = threading.Event(), threading.Event()
        original = r.port.invalidate_zoom
        def invalidate(cam):
            entered.set()
            reached(resume)
            original(cam)
        r.port.invalidate_zoom = invalidate
        self.addCleanup(resume.set)
        r.bus.emit(EventType.SEAT_SELECTED, camera=1, preset=4)
        reached(entered)
        # Service STOP bypasses the paused ordinary handler on both versions.
        self.assertTrue(RuntimeSafetyService(r.port).stop_camera('cam1').ok)
        resume.set()
        r.flush()
        self.assertEqual(r.manager.invalidations, [])

    def test_direct_absolute_zoom_paused_before_admission_is_canceled(self):
        r = self.rig()
        result, finished = [], threading.Event()
        def zoom():
            result.append(r.port.zoom_absolute('cam1', 50).ok)
            finished.set()
        thread = threading.Thread(target=zoom, daemon=True)
        r.manager.pause_thread = thread
        thread.start()
        reached(r.manager.before_admission)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(r.a.stopped)
        r.manager.resume.set()
        reached(finished)
        thread.join(TIMEOUT)
        self.assertEqual(result, [False])
        self.assertEqual(r.a.history, [])
        self.assertEqual(r.manager.invalidations, [])

    def test_bus_restart_no_second_emergency_consumer(self):
        r = self.rig()
        old_emergency = getattr(r.bus, '_emergency_worker', None)
        if old_emergency is None:
            self.skipTest('baseline has no emergency lane')
        entered, resume = threading.Event(), threading.Event()
        original = r.manager.worker
        def lookup(ip):
            if threading.current_thread() is old_emergency:
                entered.set()
                reached(resume)
            return original(ip)
        r.manager.worker = lookup
        self.addCleanup(resume.set)
        r.bus.emit(EventType.CAMERA_STOP, camera=1)
        reached(entered)
        old_normal = r.bus._worker
        with patch.object(old_emergency, 'join', return_value=None):
            r.bus.stop()
        self.assertFalse(old_normal.is_alive())
        r.bus.start()
        self.assertIs(r.bus._emergency_worker, old_emergency)
        resume.set()
        old_emergency.join(TIMEOUT)
        self.assertFalse(old_emergency.is_alive())
        r.bus.start()
        self.assertIsNot(r.bus._emergency_worker, old_emergency)
        r.bus.emit(EventType.CAMERA_STOP, camera=2)
        reached(r.b.stopped)

    def test_active_camera_default_is_captured_at_emission_other_endpoint_survives(self):
        r = self.rig()
        r.recall()
        r.state.active_camera = 2
        r.bus.emit(EventType.SEAT_SELECTED, seat_number=8)
        r.state.active_camera = 1
        self.assertTrue(RuntimeSafetyService(r.port).stop_camera('cam1').ok)
        r.a.finish_late()
        r.flush()
        self.assertEqual(len(r.a.history), 1)
        self.assertEqual(len(r.b.history), 1)
        self.assertEqual(r.state.cam2.active_preset, 8)

    def test_bus_restart_no_second_normal_consumer(self):
        r = self.rig()
        r.recall()
        old_worker = r.bus._worker
        # Replace join with a deterministic timed-out join; no two-second delay.
        with patch.object(old_worker, 'join', return_value=None):
            r.bus.stop()
        r.bus.start()
        self.assertIs(r.bus._worker, old_worker)
        r.a.finish_late()
        old_worker.join(TIMEOUT)
        self.assertFalse(old_worker.is_alive())
        r.bus.start()
        self.assertIsNot(r.bus._worker, old_worker)
        r.bus.emit(EventType.CAMERA_STOP, camera=2)
        reached(r.b.stopped)

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + unittest_args, verbosity=2)
