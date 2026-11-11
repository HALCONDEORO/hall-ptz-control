# Operator & Support Guide - Safety Actions

This guide describes safety API contracts, not a verified GUI checklist.
`RuntimeSafetyService` defines STOP and STOP ALL; `SafetyResetService` defines
runtime cleanup. The operator GUI now has a red STOP ALL button below the camera
controls. It stays accessible without an active session or a connected camera;
failed requests show a temporary red notice below it. Confirm the physical result.
Safety Reset is still a service contract, not a verified GUI control. Do not plan
an emergency response around an unverified button or command. The GUI's camera
close choices are described below.

A successful software result does not confirm physical stopping. Network loss,
a disconnected camera or a rejected command can prevent delivery. Rehearse the
installed controls and the venue's physical fallback before live use. If a
camera continues moving, follow that fallback rather than waiting for an API
reset to prove the camera is safe.

---

## Safety API contract reference

### STOP

**What it does:** Requests a priority pan/tilt/zoom stop for the camera passed to
the safety service. The caller selects the target; a software result alone is
not confirmation that the camera stopped.

**When to use:** The camera is moving and you want to stop it without affecting other cameras or the session.

**What it does NOT do:**

- Does not affect other cameras.
- Does not end the session.
- Does not clear any internal state.

---

### STOP ALL

**What it does:** Requests priority STOP for configured cameras through the
camera adapter, without requiring an active session. Delivery and the physical
result still depend on the camera and network.

**When to use:**

- All cameras need to stop at the same time (e.g. end of meeting, emergency).
- A camera is stuck moving and you are unsure which one is the problem.

**Software behavior (not a physical guarantee):**

- Bypasses the active-session guard — works even with no active session.
- Attempts every camera even if one fails; partial failure is reported.
- Drains queued movement commands so no stale move executes after the stop.

**What it does NOT do:**

- Does not end the session or put cameras into standby.
- Does not clear runtime state.

---

### SAFETY RESET

**What it does:** Requests STOP ALL and then attempts volatile session and ATEM
cleanup through the services supplied by the caller, without restarting the app
or rebooting the Raspberry Pi. It reports partial failure if a step fails; it
must not be treated as proof that all cameras are stopped.

**When to use:**

- A session or camera state is stuck and STOP / STOP ALL did not resolve it.
- After a failed command, reconnect glitch, or unexpected state.
- Support asks you to perform a safety reset to return to a known-good state.
- At the end of automated tests to verify no state leaks between runs.

**What is cleared:**

- A priority STOP is requested for configured cameras; confirm the physical result.
- Pending command queues are drained.
- Active session state (active flag, chairman name, session ID), when a session
  service is supplied and cleanup succeeds.
- Session file marker cleanup is attempted; preserve warnings if it fails.

**What is preserved (never deleted):**

- `config.yaml` — camera IPs, ATEM address, site configuration.
- `room_layout.json` — seat layout, names, roles.
- Saved presets.
- Licence and installation files.
- Any persistent customer data or logs.

**Failure handling:** session cleanup can succeed while a camera STOP fails.
Read the per-subsystem result and preserve errors. A cleared session or a second
reset is not a physical safety certificate. Runtime state cleanup uses
`movement_state="unknown"`, not a confirmed stopped state. Missing optional
services are not evidence that their corresponding state was reset.

**Repeated calls:** cleanup is designed to be repeatable, but each call can still
fail to reach hardware. Recheck the result and the actual equipment every time.

---

### EXIT — Keep cameras on

**What it does:** Closes the KH PTZ Control application without sending a camera standby or power-off command.

**When to use:**

- You need to restart the app but cameras should stay powered and in position.
- You are switching control methods and want cameras ready immediately.

---

### EXIT — Power off cameras

**What it does:** Closes the app and follows the full camera shutdown sequence (standby / power-off).

**When to use:**

- End of day, event done, or cameras need to be put into a low-power state.
- Normal planned shutdown.

---

## Which contract applies?

STOP ALL has the GUI route described above. The other service-level choices are
for support and development unless their installed route has been demonstrated.
In particular, Safety Reset has no verified operator GUI control.

| Situation | Relevant contract or installed close choice |
|---|---|
| One camera is moving, need to stop it | STOP |
| All cameras need to stop immediately | STOP ALL |
| Session state is stuck or corrupted | SAFETY RESET |
| App needs to restart, keep cameras live | EXIT — Keep cameras on |
| End of day, cameras can go to standby | EXIT — Power off cameras |
| Automated test cleanup between runs | SAFETY RESET |

---

## Support: what state is cleared vs preserved

| State | STOP | STOP ALL | SAFETY RESET |
|---|---|---|---|
| Camera movement | STOP requested for target | STOP requested for configured cameras | STOP ALL requested; verify result |
| Command queue | Drained for stopped camera | Drained for all | Drained for all |
| Session active flag | No | No | Cleared if supplied session service succeeds |
| Chairman name | No | No | Cleared if supplied session service succeeds |
| config.yaml | Never | Never | Never |
| room_layout.json | Never | Never | Never |
| Saved presets | Never | Never | Never |
| Camera standby/power-off | No | No | No |
| App process restarts | No | No | No |
| Raspberry Pi reboots | No | No | No |

---

## Notes for hardware validation

Before claiming runtime safety is pilot-ready, validate on Raspberry Pi + real
VISCA cameras. First demonstrate which installed UI or support route invokes
each contract. If Safety Reset has no verified route, mark that
check blocked; do not claim it passed from a unit test or invent a CLI command:

1. App starts on Pi.
2. Camera connects; movement works.
3. Start movement → STOP → camera stops.
4. Through a verified route, queue movement → STOP ALL → observe all cameras stop.
5. Start session → trigger movement → run Safety Reset → session inactive, app usable.
6. Disconnect camera network → invoke STOP ALL / Safety Reset through a verified
   route → app does not crash; failures are reported and no physical stop is assumed.
7. ATEM path: Safety Reset clears transient state without destructive ATEM command.
8. Close with "keep cameras on" → no standby/power-off sent.
9. Close with power-off → existing shutdown behavior preserved.

Record results in `docs/MVP_VALIDATION_REPORT.md` with date, app version, Pi model, camera model.
