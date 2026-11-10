# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Nonblocking camera start-up confirmation, separate from the main window."""

def maybe_prompt_power_on(self) -> None:
    """Preguntar al arrancar si encender las cámaras (elección del operador).

    Conforme al contrato: la sesión solo arranca si el operador confirma;
    al rechazar, las cámaras quedan como están (sin arranque automático).
    No se muestra si ya hay sesión activa o si no hay ninguna cámara con IP
    válida configurada (no habría nada que encender).
    """
    if (getattr(self, '_shutting_down', False)
            or getattr(self, 'session_active', False)):
        return
    from config import CAM1, CAM2, is_valid_ip
    if not (is_valid_ip(CAM1.ip) or is_valid_ip(CAM2.ip)):
        return

    if getattr(self, '_startup_power_prompt', None) is not None:
        return
    from PyQt5.QtWidgets import QMessageBox
    box = QMessageBox(self)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle('Camera start-up')
    box.setText('Turn on the cameras now?')
    box.setInformativeText('Start the session and turn on the cameras, or leave them as they are.')
    yes_btn = box.addButton('Turn on cameras', QMessageBox.AcceptRole)
    no_btn = box.addButton('Not now', QMessageBox.RejectRole)
    from ui.message_box_layout import fit_message_box_buttons
    fit_message_box_buttons(box)
    for button in (yes_btn, no_btn):
        button.setMinimumHeight(max(52, button.minimumHeight()))
        button.setMinimumWidth(max(220, button.minimumWidth()))
    box.setStyleSheet('QMessageBox { font-size: 18px; } '
                      'QPushButton { font-size: 16px; padding: 10px 16px; }')
    box.setDefaultButton(no_btn)
    self._startup_power_prompt = box

    def finished(_result):
        self._startup_power_prompt = None
        if (box.clickedButton() is yes_btn
                and not getattr(self, '_shutting_down', False)
                and not getattr(self, 'session_active', False)):
            # Reuse the session button path: background power I/O and
            # delayed Home are owned by its existing controller/service.
            self._session.ToggleSession()
        box.deleteLater()

    box.finished.connect(finished)
    box.open()  # asynchronous modal, no nested event loop or network in Qt
