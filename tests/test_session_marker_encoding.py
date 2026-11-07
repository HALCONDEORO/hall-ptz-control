"""A damaged interrupted-session marker must still warn, not abort startup."""
import logging

from application.session_marker import was_session_interrupted


def test_undecodable_marker_still_reports_interruption(tmp_path, caplog):
    path = tmp_path / 'session_active'
    path.write_bytes(b'\xff\xfe\x80')
    with caplog.at_level(logging.WARNING):
        assert was_session_interrupted(path) is True
    assert 'Previous session may have ended unexpectedly' in caplog.text
    assert 'unknown' in caplog.text
    assert path.read_bytes() == b'\xff\xfe\x80'
