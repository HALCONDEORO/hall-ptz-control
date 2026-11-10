"""One confirmed zoom in flight, with only the latest pending UI intent."""
import logging
import threading

from PyQt5.QtCore import QObject, Qt, pyqtSignal

logger = logging.getLogger(__name__)


class ZoomDispatcher(QObject):
    finished = pyqtSignal()

    def __init__(self, current_session, parent=None):
        super().__init__(parent)
        self._current_session = current_session
        self._running = False
        self._pending = None
        self.finished.connect(self._complete, Qt.QueuedConnection)

    def submit(self, port, camera_id, value):
        generation = self._current_session()
        if generation is None:
            return
        request = (generation, port, camera_id, value)
        if self._running:
            self._pending = request
        else:
            self._start(request)

    def _start(self, request):
        generation, port, camera_id, value = request
        if generation != self._current_session():
            return
        self._running = True

        def run():
            try:
                port.zoom_absolute(camera_id, value)
            except Exception:
                logger.exception('Confirmed zoom failed')
            finally:
                try:
                    self.finished.emit()
                except RuntimeError:
                    # The UI owner was deleted while the port call completed.
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _complete(self):
        self._running = False
        request, self._pending = self._pending, None
        if request is not None:
            self._start(request)
