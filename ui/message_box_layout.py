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
