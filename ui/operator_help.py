"""Offline operator help with the same full STOP route as ADMIN STOP ALL."""
from html import escape

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app_version import read_version
from ui.operator_help_content import TOPICS
from ui.styles import touch_scrollbar_qss


class OperatorHelpDialog(QDialog):
    def __init__(self, window):
        super().__init__(window, Qt.Dialog | Qt.FramelessWindowHint)
        self._window = window
        self.setWindowTitle('Help / Stop cameras')
        self.setWindowModality(Qt.WindowModal)
        self.setStyleSheet(
            'QDialog, QScrollArea, QScrollArea > QWidget > QWidget { background: white; }'
            'QLabel { color: #251f21; font-size: 17px; background: transparent; }'
            'QPushButton { color: #251f21; font-size: 18px; background: #f6f3f1; '
            'border: none; border-radius: 8px; padding: 6px 12px; text-align: left; }'
            'QPushButton:pressed { background: #e6dfdb; }'
            'QScrollArea { border: none; }')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 10, 20, 10)
        outer.setSpacing(8)
        heading = QHBoxLayout()
        title = QLabel('Help', self)
        title.setStyleSheet('font-size: 26px; font-weight: bold;')
        heading.addWidget(title, 1)
        self.close_button = QPushButton('X', self)
        self.close_button.setAccessibleName('Close help')
        self.close_button.setFixedSize(44, 44)
        self.close_button.clicked.connect(self.close)
        heading.addWidget(self.close_button)
        outer.addLayout(heading)
        self.stop_button = QPushButton('STOP BOTH CAMERAS\nMovement only · No confirmation', self)
        self.stop_button.setMinimumHeight(68)
        self.stop_button.setStyleSheet(
            'QPushButton { background: #ad202d; color: white; font-size: 21px; '
            'font-weight: bold; border: none; border-radius: 9px; text-align: left; padding: 8px 18px; }'
            'QPushButton:pressed { background: #781521; }')
        self.stop_button.clicked.connect(self._stop)
        outer.addWidget(self.stop_button)
        self.feedback = QLabel('Check the cameras. Sending STOP does not prove they stopped.', self)
        self.feedback.setWordWrap(True)
        self.feedback.setMinimumHeight(40)
        self.feedback.setStyleSheet('color: #9c2029; font-size: 16px;')
        self.feedback.setAccessibleName('Camera stop result')
        outer.addWidget(self.feedback)
        self.pages = QStackedWidget(self)
        outer.addWidget(self.pages, 1)
        self.topic_buttons = []
        index = QWidget(self.pages)
        grid = QGridLayout(index)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for number, (name, _) in enumerate(TOPICS):
            button = QPushButton(name + '   >', index)
            button.setMinimumHeight(48)
            button.clicked.connect(lambda _checked=False, n=number: self._show_topic(n))
            grid.addWidget(button, number // 2, number % 2)
            self.topic_buttons.append(button)
        self.status_button = QPushButton('Status and version   >', index)
        self.status_button.setMinimumHeight(48)
        self.status_button.clicked.connect(self._show_status)
        grid.addWidget(self.status_button, 4, 0, 1, 2)
        self.pages.addWidget(index)
        detail = QWidget(self.pages)
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(0, 0, 0, 0)
        self.back_button = QPushButton('<  All topics', detail)
        self.back_button.setMinimumHeight(44)
        self.back_button.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        layout.addWidget(self.back_button)
        self.scroll = QScrollArea(detail)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().setStyleSheet(touch_scrollbar_qss())
        self.scroll.verticalScrollBar().setFixedWidth(32)
        self.body = QLabel(self.scroll)
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.body.setContentsMargins(4, 4, 14, 12)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)
        self.pages.addWidget(detail)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    def showEvent(self, event):
        self.feedback.setText('Check the cameras. Sending STOP does not prove they stopped.')
        self.pages.setCurrentIndex(0)
        self.close_button.setFocus()
        super().showEvent(event)

    def _show_topic(self, number):
        title, sections = TOPICS[number]
        text = f'<h2>{escape(title)}</h2>'
        for heading, body in sections:
            text += f'<p><b>{escape(heading)}</b><br>{escape(body)}</p>'
        self._show_detail(text)

    def _show_detail(self, text):
        self.body.setText(text)
        self.pages.setCurrentIndex(1)
        self.scroll.verticalScrollBar().setValue(0)

    def _show_status(self):
        # Read existing state only: no sockets, probes, diagnostics or commands.
        lines = [f'Version: {escape(read_version())}',
                 'Snapshot when opened. Connection is not proof of physical stopping.']
        cameras = getattr(self._window, '_cameras', None)
        for number in (1, 2):
            try:
                connected = cameras.is_connected(cameras.ip_for_key(number))
                state = 'Connected (reported)' if connected else 'Not connected / unknown'
            except Exception:
                state = 'Unknown'
            lines.append(f'Camera {number}: {state}')
        self._show_detail('<h2>Status and version</h2><p>' + '<br>'.join(lines) + '</p>'
                          '<p>Read-only. No settings, passwords or network tests. '
                          'Go back and reopen this topic to refresh the snapshot.</p>')

    def _stop(self):
        from ui.stop_all_wiring import request_camera_stop
        try:
            result = request_camera_stop(self._window)
            ok = result is not None and result.ok
        except Exception:
            ok = False
        self.feedback.setText(
            'STOP sent. Physical stopping is not confirmed. Check both cameras.' if ok else
            'Could not confirm STOP delivery. Check both cameras and use the local fallback.')


class _HelpEntry(QObject):
    """Quiet corner icon with a larger, non-overlapping touch area."""
    def __init__(self, window):
        panel = window._right_panel._container
        super().__init__(panel)
        self.window = window
        self.dialog = None
        self.button = QPushButton('?', panel)
        self.button.setFixedSize(48, 48)
        self.button.setAccessibleName('Help / Stop cameras')
        self.button.setToolTip('Help / Stop cameras')
        self.button.setStyleSheet(
            'QPushButton { color: #9b9796; font-size: 22px; background: transparent; border: none; }'
            'QPushButton:pressed { background: #eae9ea; border-radius: 8px; }')
        self.button.clicked.connect(self.open)
        # Reserve an actual footer row. Absolute positioning can overlap the
        # Admin Mode row after RightPanel's deferred layout pass.
        panel.layout().addWidget(self.button, 0, Qt.AlignRight)

    def open(self):
        if self.dialog is None:
            self.dialog = OperatorHelpDialog(self.window)
        screen = self.window.screen().availableGeometry()
        width, height = min(1000, screen.width()), min(600, screen.height())
        self.dialog.resize(width, height)
        self.dialog.move(screen.x() + (screen.width() - width) // 2,
                         screen.y() + (screen.height() - height) // 2)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()


def connect_operator_help(window):
    window._operator_help = _HelpEntry(window)
