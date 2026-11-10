# Camera compatibility evidence and protocol expansion

A protocol name is not a verified camera model. The production adapter is
VISCA-over-IP; ONVIF and Pelco are not implemented. Do not advertise them as
supported. The current installation guide describes TCP port 5678; that is not
a universal port for every VISCA camera.

## Per-model profile records

Use `config/examples/camera-compatibility-template.json` as an evidence record,
not as runtime configuration. It is intentionally NOT consumed by the loader.
Create one reviewed record per exact manufacturer/model/firmware combination.
Do not select a brand profile automatically from a similar model name.

Before enabling a model record in a future runtime change, verify:

- transport and framing (raw TCP, UDP or vendor-specific framing), port and ID;
- pan/tilt/zoom speed ranges, direction and safe stop bytes;
- preset numbering, limits and whether recall completion is observable;
- ACK/completion/error behavior, timeout and retry policy;
- disconnect/reconnect, cancellation, STOP priority and no delayed movement;
- standby/power behavior and unsupported-command handling.

Test protocol bytes with synthetic fixtures first. On hardware use an authorised
clear area, an available STOP control and explicit operator attendance. A record
stays `unverified` until exact-device evidence is independently reviewed. A
similar camera's result does not transfer to another firmware/model.

## Proposed ONVIF adapter (design only)

Implement a separate adapter behind `ports.camera_port.CameraPort`; keep sockets
and ONVIF authentication out of application services and the UI. Start with
status, continuous move/zoom, stop and preset recall. Query capabilities and map
unsupported operations to a clear CommandResult error, never an invented success.

ONVIF preset tokens are not VISCA integer slots. Keep an explicit mapping and do
not cast arbitrary tokens to integers. Preserve stop_all's best-effort behavior
for all cameras even when one is unreachable. Use a fake transport in tests and
verify timeout, cancel, reconnect and stop ordering before physical acceptance.
Do not add discovery multicast, remote-control bots or automatic movement as a
side effect of adding the adapter. No ONVIF dependency, secret or network access
is added by this document.

## Installation compatibility boundary

The product baseline uses OS packages (`apt`), including PyQt5, QtSvg and PyYAML.
Do not add global pip commands or `--break-system-packages` to solve Bookworm's
externally-managed Python restriction. Keep system GUI mode as the default.

ATEM and developer tooling remain optional and outside the standard path.
A future optional-package change should use a dedicated virtual environment,
explicit interpreter and pinned reviewed dependency set, with tests that prove
base PTZ works when the option is absent or fails. This is a design gate, not an
implemented installer switch. Do not copy a new environment over system Python.
ATEM licence/distribution and exact-model hardware gates remain in
`ATEM_DEPENDENCY_DECISION.md`. No installer or appliance changes are made here.
