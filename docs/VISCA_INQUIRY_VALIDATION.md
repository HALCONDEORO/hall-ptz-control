# Exposure inquiry observations

AE and exposure-compensation parsers require the complete expected inquiry
shape: camera response header, 0x50 response byte, exact payload length and FF
terminator. Missing/extra bytes and wrong response types return unknown.

Supported AE codes are 00 (full auto), 03 (manual), 0A (shutter priority),
0B (iris priority) and 0D (bright). The existing UI groups the priority modes
with auto controls. An unrecognized code no longer invents an auto observation
or starts the follow-up compensation inquiry. Existing observed state is retained
rather than replaced by a guessed mode.

Protocol reference checked during this change:
https://docs.ptzoptics.com/resources/visca-api/inquiries/

This is parser/adapter validation only. It does not claim compatibility with all
vendor-specific AE modes, change default UI state or prove camera hardware works.
Legacy exposure range clamping and transport framing policies are unchanged.
