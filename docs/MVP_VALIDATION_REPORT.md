# MVP Hardware Validation Report — Runtime Safety

> Fill in this template when running the smoke matrix on Raspberry Pi + real hardware.
> Reference: issue #785 / epic #778.

---

## Hardware under test

| Field | Value |
|---|---|
| Date | |
| App version | |
| Raspberry Pi model | |
| Camera model | |
| ATEM model / substitute | |
| Tester | |

---

## Smoke matrix

This is a blank template, not recorded hardware acceptance. STOP ALL is available
only in ADMIN. USER has no dedicated per-camera/all-camera STOP button; joystick
release requests STOP for the moved camera, not automatic preset cancellation.
Confirm an accessible physical fallback before testing. Safety Reset remains a
service contract without a verified operator GUI control.


| # | Scenario | Expected | Result | Notes |
|---|---|---|---|---|
| 1 | App starts on Raspberry Pi | App opens without error | | |
| 2 | Camera connects | Camera shows Connected status | | |
| 3 | USER manual joystick movement → release joystick | Camera stops moving | | |
| 4 | ADMIN: queue movement → press STOP ALL | All cameras stop | | |
| 5 | Start session → queue movement/preset → Safety Reset | Session inactive, app still usable | | |
| 6 | Safety Reset run twice (idempotency) | No crash; record partial failures and unknown movement, not assumed safe state | | |
| 7 | ADMIN: disconnect camera network → STOP ALL → verified Safety Reset route | App does not crash, errors reported cleanly | | |
| 8 | ATEM path: Safety Reset clears transient state | No destructive ATEM command sent | | |
| 9 | Close app — "Salir sin apagar cámaras" | App closes, no standby/power-off sent | | |
| 10 | Close app — "Salir y apagar cámaras" | App closes, cameras go to standby | | |

### Results key: PASS / FAIL / SKIP (hardware not available)

---

## Failures

> List any FAIL results with follow-up issue numbers.

| # | Description | Follow-up issue |
|---|---|---|
| | | |

---

## Sign-off

Validated by: _______________  
Date: _______________  
Ticket closed: #785
