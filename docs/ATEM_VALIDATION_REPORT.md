# ATEM Hardware Validation Report (#557)

**Template: NOT RUN.** Complete one copy per installation or revalidation event.
Blank fields and unselected PASS/FAIL choices are not validation evidence. No
model or firmware is approved merely because it appears in an installation guide.

---

## Environment

| Field | Value |
|---|---|
| Date | |
| Validator | |
| KHPTZ version and commit/tag | |
| Raspberry Pi model | |
| Raspberry Pi OS version | |
| ATEM model | |
| ATEM firmware version | |
| PyATEMMax version and dependency/licence review reference | |
| Network topology | |

---

## Test Matrix

### Connectivity

| Test | Result | Notes |
|---|---|---|
| Pi can ping ATEM IP | PASS / FAIL / SKIP | |
| Running adapter receives fresh ATEM state after startup | PASS / FAIL / SKIP | |
| CLI named ATEM network check: record output, exit code and limitations | PASS / FAIL / SKIP | |
| ATEM reconnects after disconnect/reconnect | PASS / FAIL / SKIP | |

### Program / Preview display

| Test | Result | Notes |
|---|---|---|
| Correct input labels shown | PASS / FAIL / SKIP | |
| Program input changes reflected in UI | PASS / FAIL / SKIP | |
| Preview input changes reflected in UI | PASS / FAIL / SKIP | |
| Incorrect mapping shows identifiable mismatch | PASS / FAIL / SKIP | |

### Manual Admin Commands (TECHNICIAN role only)

| Test | Result | Notes |
|---|---|---|
| `set_preview_input` changes ATEM preview bus | PASS / FAIL / SKIP | |
| CUT transitions program correctly | PASS / FAIL / SKIP | |
| AUTO transitions with configured transition effect | PASS / FAIL / SKIP | |
| CUT/AUTO blocked for camera_operator role | PASS / FAIL / SKIP | |
| CUT/AUTO greyed out in UI for non-technician | PASS / FAIL / SKIP | |

### Failure / Degraded

| Test | Result | Notes |
|---|---|---|
| Startup with ATEM disconnected (no hang) | PASS / FAIL / SKIP | |
| Startup with wrong ATEM IP (no hang) | PASS / FAIL / SKIP | |
| Camera PTZ works while ATEM offline | PASS / FAIL | |
| Offline ATEM diagnostic result recorded separately from GUI behaviour | PASS / FAIL / SKIP | |
| Reconnect after power-cycle | PASS / FAIL / SKIP | |
| ATEM Software Control coexistence | PASS / FAIL / N/A | |

### Automation Safety

| Test | Result | Notes |
|---|---|---|
| CALL preset does NOT trigger ATEM CUT/AUTO | PASS / FAIL | |
| SET preset does NOT trigger ATEM CUT/AUTO | PASS / FAIL | |
| Reconnect does NOT trigger CUT/AUTO | PASS / FAIL | |
| `automation_disabled: true` confirmed in config | PASS / FAIL | |

---

## Evidence and safe-test scope

Record permission to use the equipment, the non-live output used for CUT/AUTO,
observed results and timestamps. Capture synthetic input labels or redact site
addresses and names before uploading evidence. Never include secrets. If a test
was not run, mark SKIP with a reason; never infer PASS from a blank or a mock.

## Summary

| Field | Value |
|---|---|
| Overall result | PASS / PASS WITH LIMITATIONS / FAIL |
| Customer-ready? | YES / NO / NOT YET |
| Blocking issues | |
| Accepted limitations | |
| Next revalidation trigger | firmware update / PyATEMMax update / model change |
