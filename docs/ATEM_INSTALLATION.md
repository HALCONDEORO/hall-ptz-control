# ATEM Installation, Troubleshooting and Handover (#556)

## Overview

Phase 1 KH PTZ Control ATEM support is **read-only monitoring + manual admin switching only**.
Automatic ATEM switching is **disabled by default** and must not be enabled without validated safety testing.

The camera-control path is intended to remain available when ATEM is offline.
Confirm this on the actual installation; it is not a blanket hardware guarantee.

**Evidence status:** [ATEM_VALIDATION_REPORT.md](ATEM_VALIDATION_REPORT.md) is an
uncompleted template, not a list of validated models or firmware. No physical
ATEM validation is established by this guide or by mocked tests.

---

## Prerequisites

| Requirement | Details |
|---|---|
| ATEM model | Record the exact model; Mini / Mini Pro / Mini ISO are candidates, not validated models in the blank report |
| Network | ATEM and Raspberry Pi on the same AV subnet (e.g. 192.168.30.0/24). Static IPs required. |
| PyATEMMax | Optional Python dependency — required for production real-hardware monitoring. Not needed for demo/simulation. |
| Firmware | Record the actual firmware; the report template contains no tested version |
| KHPTZ version | ≥ 3.38.2 |

---

## Canonical Config (`config.yaml`)

```yaml
atem:
  ip: 192.168.30.100        # ATEM IP address
  installed: true           # ATEM physically connected to network
  enabled: true             # Active monitoring enabled
  disabled_reason: ""       # Set if temporarily disabled
  me_index: 0               # M/E bank index (0 = M/E 1, 1 = M/E 2)
  input_labels:
    1: Platform
    2: Comments
    3: Chairman
    4: None
  connect_timeout_secs: 10
  reconnect_timeout_secs: 30
  automation_disabled: true  # MUST remain true in Phase 1
```

### Validation rules
- `installed: false + enabled: true` → config rejected at startup.
- `installed: true` alone does not open a connection.
- `enabled: true` activates monitoring.
- `automation_disabled: true` **must** remain set in Phase 1. Never change without safety review.

---

## Network and Environment

- Use a dedicated AV VLAN for ATEM and PTZ cameras.
- ATEM IP must be reachable from the Pi: `ping <atem_ip>`.
- No internet required.
- ATEM Software Control may coexist — see validation report for tested coexistence.

---

## Installation Steps

Before enabling an adapter, pass the [dependency and licence review](ATEM_DEPENDENCY_DECISION.md).
PyATEMMax 1.0b9 is GPL v3, not MIT. Use the reviewed package and the approved
application revision. Configure only equipment you are authorised to test,
outside a live meeting. Keep automatic switching disabled.

1. Connect ATEM to AV network. Assign a static IP.
2. Set `atem.ip` in `/etc/khptz/config.yaml`.
3. Set `atem.installed: true` and `atem.enabled: true`.
4. Set `atem.input_labels` to match physical input wiring.
5. Run `khptz doctor` and preserve its exact output and exit code. An absent
   ATEM check is not a PASS; the current network check is gated by
   `features.atem_enabled`. See [diagnostic limits](#what-a-diagnostic-result-proves).
6. Confirm fresh Program/Preview updates in the running application. Test
   manual switching only on a safe test output with permission; a CUT/AUTO
   changes the programme, not just a local indicator.
7. Complete `docs/ATEM_VALIDATION_REPORT.md` with the exact model, firmware,
   dependency and application revisions and observed outcomes.

---

## What a diagnostic result proves

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| `ping` replies | IP reachability with ICMP at that time | ATEM protocol, correct input mapping or safe switching |
| PyATEMMax import succeeds | The package can be imported in that Python environment | A connected physical switcher or matching firmware API |
| CLI `atem_reachable` check | Result of the configured network probe | Fresh Program/Preview state or successful CUT/AUTO |
| Application shows fresh Program/Preview changes | The running adapter is receiving state for the observed test | Correct behaviour after every reconnect, power cycle or firmware change |
| Completed physical test matrix | Results for the recorded equipment and revision | Universal support for another model, firmware or installation |

The CLI constructs `DiagnosticsService`; its network ATEM check uses
`features.atem_enabled`. The separate `AtemDiagnosticsService.doctor_check`
can report an adapter's connected state, but its existence does not mean the
CLI has tested that adapter. Read the named check and evidence, rather than
assuming every `OK` means a real ATEM session is working.

A network probe warning can reflect a probe limitation as well as equipment
availability. Compare it with actual application state and record the discrepancy;
do not bypass a readiness failure or alter the network just to obtain green output.

Code references: [CLI](../runtime/cli.py),
[diagnostics](../application/diagnostics_service.py),
[network checks](../application/network_diagnostics.py),
[adapter diagnostics](../application/atem_diagnostics_service.py).

## Handover Fields

Record at install handover:

| Field | Value |
|---|---|
| ATEM model | |
| ATEM firmware version | |
| IP address | |
| M/E bank index | |
| Input 1 label | |
| Input 2 label | |
| Input 3 label | |
| Input 4 label | |
| PyATEMMax version (if used) | |
| Test result | PASS / PASS WITH LIMITATIONS / FAIL |
| Tested by | |
| Date | |

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `atem_reachable` warning | Configured probe did not succeed, or address missing | Preserve evidence; check config and actual adapter state before changing anything |
| "ATEM disconnected" in UI | Power, address, network or adapter failure | Check power/address/logs; do not power-cycle a live switcher without permission |
| `atem.enabled=true requires atem.installed=true` | Config mismatch | Set `installed: true` or `enabled: false` |
| CUT/AUTO greyed out in admin panel | Not TECHNICIAN role | Switch to admin/technician mode |
| Camera controls unavailable | Session not started | ATEM state does not block PTZ — check session |

---

## Disabled / Degraded Behaviour

- Camera PTZ is designed to remain independent of ATEM availability; verify
  actual degraded behaviour during the installation test.
- Degraded wording: **"ATEM unavailable — camera controls unaffected"**.
- Distinguish a network-probe warning from the running adapter's connection state.
- A missing check or omitted section means no evidence from that check, not a PASS.

---

## Firmware / Software Update Policy

Any change to ATEM firmware or PyATEMMax version requires:

1. Re-run ATEM hardware smoke matrix (see `docs/ATEM_VALIDATION_REPORT.md`).
2. Update validation report with new version and date.
3. Do not claim customer-ready status until revalidation passes.

---

## Brand / Legal Wording

*ATEM is a registered trademark of Blackmagic Design Pty. Ltd.*
*KH PTZ Control is not affiliated with or endorsed by Blackmagic Design.*
