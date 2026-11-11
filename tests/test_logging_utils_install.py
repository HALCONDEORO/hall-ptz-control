"""Regression tests for install_repeated_message_filter handler sharing.

Bug: the installer used to add ONE RepeatedMessageFilter instance to every
root handler. The filter keeps its dedup state per instance, so the first
handler that saw a record consumed the "first occurrence" and every later
handler in the chain dropped that same record as a "repeat". In production
that meant the rotating file log silently lost the WARNING/ERROR records
the console had just emitted; in tests it emptied pytest's caplog handler
whenever main() had run earlier in the process (test_main_startup ->
test_session_service interference).
"""

from __future__ import annotations

import logging

from core.logging_utils import install_repeated_message_filter


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _logger_with_handlers(name: str, n: int):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handlers = [_ListHandler() for _ in range(n)]
    for h in handlers:
        logger.addHandler(h)
    return logger, handlers


class TestPerHandlerInstances:
    def test_every_handler_receives_the_first_occurrence(self):
        logger, handlers = _logger_with_handlers("test.rmf.first", 2)
        try:
            install_repeated_message_filter(logger)
            logger.error("unique message alpha")
            for h in handlers:
                assert h.messages == ["unique message alpha"]
        finally:
            for h in handlers:
                logger.removeHandler(h)

    def test_each_handler_dedups_independently(self):
        """The 2nd identical record is dropped on ALL handlers; the 10th is
        summarised on ALL handlers — same behaviour as a single handler."""
        logger, handlers = _logger_with_handlers("test.rmf.dedup", 2)
        try:
            install_repeated_message_filter(logger, summary_every=3)
            for _ in range(4):
                logger.error("unique message beta")
            for h in handlers:
                assert len(h.messages) == 2, h.messages          # 1st + summary
                assert h.messages[0] == "unique message beta"
                assert h.messages[1].startswith("Previous log message repeated")
        finally:
            for h in handlers:
                logger.removeHandler(h)

    def test_install_returns_the_filters(self):
        logger, handlers = _logger_with_handlers("test.rmf.return", 2)
        try:
            installed = install_repeated_message_filter(logger)
            assert len(installed) == 2
            assert len({id(f) for f in installed}) == 2  # distinct instances
        finally:
            for h in handlers:
                logger.removeHandler(h)
