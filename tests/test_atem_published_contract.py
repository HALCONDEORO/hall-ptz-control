"""Model the published 1.0b9 constant shape, not callable IntEnum mocks.

No upstream code is copied and no network connection is opened.
"""
from types import SimpleNamespace
from unittest.mock import Mock

from adapters.atem_values import source_number, video_sources
from adapters.atem_write_adapter import ATEMWriteAdapter


class Constant:
    def __init__(self, value):
        self.value = value


class SourceList:
    def __iter__(self):
        return iter([Constant(1), Constant(2)])


def test_published_constants_are_not_int_enums():
    module = SimpleNamespace(ATEMVideoSources=SourceList)
    assert [source_number(source) for source in video_sources(module)] == [1, 2]
    assert source_number(3) == 3


def test_adapter_reads_constant_values_and_sends_numeric_preview():
    adapter = ATEMWriteAdapter(ip="192.0.2.1")
    switcher = SimpleNamespace(
        programInput={0: SimpleNamespace(videoSource=Constant(1))},
        previewInput={0: SimpleNamespace(videoSource=Constant(2))},
        setPreviewInputVideoSource=Mock(),
    )
    adapter._connected = True
    adapter._atem = switcher
    adapter._pyatemmax = SimpleNamespace(ATEMVideoSources=SourceList)
    assert adapter.get_program_input() == 1
    assert adapter.get_preview_input() == 2
    assert adapter.test_connection().ok
    assert adapter.set_preview_input(2).ok
    switcher.setPreviewInputVideoSource.assert_called_once_with(0, 2)
