# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Normalize published PyATEMMax constants without assuming IntEnum semantics."""
from __future__ import annotations


def source_number(source) -> int:
    """1.0b9 uses constants with .value; isolated adapters may return plain ints."""
    return int(getattr(source, "value", source))


def video_sources(module):
    """The published API exports a list class, not an iterable enum class."""
    sources = module.ATEMVideoSources
    return sources() if isinstance(sources, type) else sources
