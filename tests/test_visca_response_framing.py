# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Reject malformed/truncated transport responses without inventing success."""

import pytest

from ptz.visca.parser import (
    contains_completion,
    contains_final_response,
    validate_visca_response,
)


@pytest.mark.parametrize("response", [
    b"\x90\x51",                 # truncated Completion
    b"\x00\x51\xff",           # not a camera response header
    b"\x81\x51\xff",           # controller header, not a response
    b"\xff\x51\xff",           # terminator is not a response header
    b"\x90\x61\xff",           # Error without its error-code byte
])
def test_malformed_response_is_not_terminal_or_successful(response):
    assert not contains_final_response(response)
    assert not contains_completion(response)
    assert not validate_visca_response(response)[0]


@pytest.mark.parametrize("response", [
    b"\x90\x51\xff",
    b"\x90\x41\xff\x90\x51\xff",
    b"\x90\x50\x00\x01\x02\x03\xff",  # inquiry data
])
def test_complete_response_remains_accepted(response):
    assert contains_final_response(response)
    assert contains_completion(response)
    assert validate_visca_response(response)[0]


def test_complete_error_is_terminal_but_not_success():
    response = b"\x90\x61\x41\xff"
    assert contains_final_response(response)
    assert not contains_completion(response)
    assert not validate_visca_response(response)[0]
