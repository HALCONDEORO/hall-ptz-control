"""Run a bounded camera diagnostic sequence without blocking the Qt owner."""
import logging
import threading

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class CameraDiagnosticRunner(QObject):
    result = pyqtSignal(int, bool)
    complete = pyqtSignal()
    _done = pyqtSignal(int, bool)

    def __init__(self, owner, port, camera_id, commands):
        super().__init__(owner)
        self._port = port
        self._camera_id = camera_id
        self._commands = tuple(commands)
        self._cancelled = threading.Event()
        self._step = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next)
        self._done.connect(self._apply, Qt.QueuedConnection)
        owner.finished.connect(self.cancel)
        owner.destroyed.connect(self.cancel)

    def start(self):
        self._timer.start(100)

    def cancel(self, *_args):
        self._cancelled.set()
        self._timer.stop()

    def _next(self):
        if self._cancelled.is_set():
            return
        if self._step == len(self._commands):
            self.complete.emit()
            return
        method_name, indicator = self._commands[self._step]

        def run():
            if self._cancelled.is_set():
                return
            ok = False
            try:
                if self._port is not None:
                    result = getattr(self._port, method_name)(self._camera_id)
                    ok = bool(getattr(result, 'ok', False))
            except Exception:
                logger.exception('Camera diagnostic %s failed', method_name)
            if not self._cancelled.is_set():
                try:
                    self._done.emit(indicator, ok)
                except RuntimeError:
                    # The dialog may be deleted while the port call returns.
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _apply(self, indicator, ok):
        if self._cancelled.is_set():
            return
        self.result.emit(indicator, ok)
        self._step += 1
        self._timer.start(100 if self._step == len(self._commands) else 500)
