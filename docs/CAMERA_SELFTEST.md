# Camera and panel regression self-test

Run after installing an approved version:

```bash
khptz selftest
```

For structured results:

```bash
khptz selftest --json
```

From a source checkout, use `python3 -m runtime.cli selftest`.

This is an offline software regression check. It uses a loopback VISCA simulator
and an offscreen Qt panel. It does not send commands to the configured cameras,
change camera presets, restart the service, or change site configuration.
No pytest installation is needed to run the command.

The panel check clicks five real Qt seat buttons, checks recall dispatch, then
simulates a control-channel cut longer than the former 1.8-second hide delay.
The panel must stay visible. Movement controls must be disabled while the
connection is unavailable, with a reconnect message, and recover on reconnection.
A successful run does not certify the physical cameras, firmware, cabling,
video feed, or every future operation.

Exit status is 0 only when all checks pass. On failure, keep the output for
support. Do not change camera addresses, ports, presets, or timeout settings to
make the test pass.

CI runs the same command, in addition to the focused worker and Qt tests.
