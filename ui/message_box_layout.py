"""Content-sized custom QMessageBox buttons across platform fonts and DPI."""


def fit_message_box_buttons(box) -> None:
    """Account for real font metrics plus padding, not a fixed 90px guess."""
    box.ensurePolished()
    for button in box.buttons():
        button.ensurePolished()
        # QSS layout caches may have measured before the final font was polished.
        # Explicit content minimums keep text intact on the Pi's fallback font.
        lines = button.text().replace('&', '').splitlines() or ['']
        metrics = button.fontMetrics()
        width = max(metrics.horizontalAdvance(line) for line in lines) + 48
        height = len(lines) * metrics.height() + 20
        button.setMinimumSize(max(button.sizeHint().width(), width),
                              max(button.sizeHint().height(), height))
    box.adjustSize()


def destructive_message_button_qss() -> str:
    return (
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            " stop:0 #C0141F, stop:1 #8E0F18); border: none; border-radius: 9px;"
            " padding: 7px 16px; min-width: 90px; min-height: 36px;"
            " font-size: 13px; font-weight: bold; font-family: 'Inter Tight'; color: white; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            " stop:0 #d41828, stop:1 #a01020); }"
    )
