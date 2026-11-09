# KH PTZ Control — Raspberry Pi Runtime Baseline

This document is the compatibility matrix for Raspberry Pi installations.
It defines the supported hardware, OS, Python version and dependency policy
for MVP installations and Raspberry Pi release-candidate validation.

**Authoritative source**: this file.  
**Related**: `docs/INSTALL_RPI.md` (step-by-step install), `docs/DEPENDENCY_PINNING_POLICY.md`.  
**Validation gate**: `docs/MVP_VALIDATION_REPORT.md`.

**Two software targets, both with physical validation pending**:

- **Legacy baseline**: Raspberry Pi OS Bullseye (Debian 11) 64-bit, Python 3.9.2,
  Raspberry Pi 4 — the original MVP target.
- **Installation target**: Raspberry Pi OS Bookworm (Debian 12) 64-bit, Python 3.11,
  Raspberry Pi 4 or 5 — rehearsed in a container, not yet on hardware. This is the
  target for new installations.

Neither target has completed physical Raspberry Pi validation. Anything marked
"software target" describes rehearsed compatibility, not a validation result.

---

## Hardware targets, not physical validation results

| Hardware | Status | Notes |
|---|---|---|
| Raspberry Pi 4 Model B (2 GB RAM) | Software target, physical validation pending | Minimum target for MVP. |
| Raspberry Pi 4 Model B (4 GB / 8 GB RAM) | Software target, physical validation pending | Preferred validation target. |
| Raspberry Pi 5 | Software target, physical validation pending | Requires Bookworm 64-bit (not Bullseye). Needs an X11 session; Bookworm defaults to Wayland. |
| Raspberry Pi 3 Model B+ | Not supported | Insufficient RAM for PyQt5 UI reliably. |
| Raspberry Pi Zero / CM | Not supported | Insufficient performance. |

**Minimum RAM**: 2 GB.  
**Minimum storage**: 16 GB microSD (Class 10 / A1 or better).

---

## Supported operating system

| OS | Status | Notes |
|---|---|---|
| Raspberry Pi OS Bullseye (Debian 11) 64-bit | Software target — legacy baseline | Ships **Python 3.9.2**; PyQt5 available via `apt`. Still supported for existing installs. |
| Raspberry Pi OS Bookworm (Debian 12) 64-bit | Software target — installation target | Ships **Python 3.11**; PyQt5 available via `apt`. Rehearsed in a container; physical validation pending. Defaults to a Wayland session: the GUI units require X11. |
| Raspberry Pi OS Bookworm 32-bit | Not validated | May work; not a test target. |
| Ubuntu 22.04 (Pi edition) | Not validated | May work for development; not a support target. |
| Generic Debian 12 (non-Pi) | CI approximation only | Used in GitHub Actions CI; not a customer deployment target. |

**Recommended image for new installations**: Raspberry Pi OS Bookworm (Debian 12), 64-bit, **Desktop with an X11 session** for this GUI workflow. Bookworm boots to Wayland by default; the GUI units require X11, so select X11 via `sudo raspi-config` -> Advanced Options -> Wayland -> X11 and reboot before installing. Bullseye (Debian 11) 64-bit Desktop remains the supported legacy baseline. Lite needs a separately reviewed display/session setup.
Use the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to write the image.

---

## Python version

**Two supported Python targets**: **3.9.2** (system Python of the Bullseye
legacy baseline) and **3.11** (system Python of the Bookworm installation
target). The codebase stays 3.9-compatible: it uses
`from __future__ import annotations` and avoids 3.10+ runtime syntax
(no `match`/`case`, no runtime `X | Y` unions), so one codebase serves both.

| Python version | Status | Notes |
|---|---|---|
| **3.9.2** | **Supported** — legacy baseline | Ships with Raspberry Pi OS Bullseye; used in CI. Software compatibility target, not a physical validation result. |
| 3.9.x (> 3.9.2) | Supported | Same minor line; expected to behave identically. |
| **3.11** | **Supported** — installation target | Ships with Raspberry Pi OS Bookworm; install rehearsal runs in a container. Physical validation pending. |
| 3.10 / 3.12 | Not validated | May work (code is 3.9-compatible), but not a target. Do not assume pilot readiness without re-validating. |
| 3.8 and below | Not supported | Uses `from __future__ import annotations` and other 3.9+ syntax. |

**Install via system package manager.** Do not use `pyenv`, `conda` or `asdf` on production
Pi installs. System Python from `apt` avoids virtualenv conflicts with PyQt5.

---

## System (apt) dependencies

Required on all installs:

```bash
sudo apt update
sudo apt install -y git rsync python3-pyqt5 python3-pyqt5.qtsvg python3-yaml x11-xserver-utils
```

| Package | Version | Purpose |
|---|---|---|
| `python3-pyqt5` | 5.15.x (both targets) | PyQt5 GUI framework |
| `python3-pyqt5.qtsvg` | 5.15.x | SVG icon rendering |
| `git` | 2.30+ | Repository clone and update |
| `rsync` | 3.2.x | Application file installation |

Optional for ATEM installs, only after licence/dependency review and on the
Bullseye target (do not run system pip on Bookworm/Trixie):

```bash
sudo apt install -y python3-pip
pip3 install -r requirements-atem.txt
```

---

## Python (pip) dependencies

**Runtime** (`requirements-rpi.txt`): intentionally empty for Raspberry Pi installs.  
All runtime dependencies are provided by `apt` on Raspberry Pi OS.

**PyYAML and PyQt5** are listed in `requirements.txt` for development machines where
`apt` may not be available (e.g. macOS or Windows dev workstations). On Raspberry Pi,
use the `apt` versions above instead.

```bash
# Raspberry Pi: no pip packages required at runtime
# (PyQt5 installed via apt above)
```

**Optional ATEM** (`requirements-atem.txt`):

```text
PyATEMMax    # optional; see requirements-atem.txt and licence review gate
```

Install only for a reviewed ATEM-enabled deployment. The published distribution
is GPL, not the previously documented MIT. See [dependency review](ATEM_DEPENDENCY_DECISION.md). If the package is absent,
ATEM monitoring is disabled and the application continues to run.

---

## ATEM dependency policy

| Condition | Behaviour |
|---|---|
| `PyATEMMax` installed and `features.atem_enabled: true` | ATEM connection active |
| `PyATEMMax` installed and `features.atem_enabled: false` | ATEM connection disabled (feature flag wins) |
| `PyATEMMax` not installed | ATEM monitoring disabled; application starts normally; `khptz doctor` reports `ATEM library not available` |

**Rule**: missing `PyATEMMax` must never prevent the application from starting.
The ATEM import is guarded at runtime.

---

## Development and CI approximation

CI uses Ubuntu + Python 3.9 (matching the 3.9.2 target line), which approximates
the Raspberry Pi OS Bullseye Python runtime but is **not** equivalent to real
hardware validation.

| Environment | Approximates | Limitations |
|---|---|---|
| GitHub Actions CI (ubuntu-latest, Python 3.9) | Bullseye Python runtime (3.9.2 legacy target) | No Pi CPU, no real touchscreen, no real camera/ATEM |
| Debian 12 container rehearsal (installer CI) | Bookworm packaging and install flow (3.11 target) | No Pi CPU, no graphical desktop session, no real hardware |
| macOS / Windows dev workstation | PyQt5 via pip; use Python 3.9 to match target | Not a deployment target; ATEM and camera hardware not present |
| Real Raspberry Pi 4 (Bullseye 64-bit) or Pi 4/5 (Bookworm 64-bit) | Legacy or installation software target | Physical validation through #381 still required |

CI passing does **not** imply pilot readiness. Real Raspberry Pi validation through
`#381` is required before claiming pilot/customer readiness.

---

## Runtime version checks (`khptz doctor`)

`khptz doctor` should report incompatible runtime versions. Intended checks for the two software targets (the matching doctor/readiness changes must also be installed):

| Check | Pass condition | Failure action |
|---|---|---|
| Python version | 3.9.x on Bullseye (legacy) or 3.11.x on Bookworm (installation target) | PASS for the matching software target only; WARNING on 3.10 or 3.12+ and other unvalidated combinations; FAIL below 3.9. This does not validate physical hardware. |
| PyQt5 import | Available | FAIL — application cannot start |
| PyQt5 SVG import | Available | WARNING |
| PyATEMMax import | Available when `atem_enabled: true` | WARNING (application still runs) |
| config.yaml readable | Parses without `ConfigError` | FAIL with field_path and remediation |
| Data directory | Writable | WARNING |

---

## Unsupported combinations

| Combination | Reason |
|---|---|
| Python 3.8 on any OS | `from __future__ import annotations` and other 3.9+ syntax used |
| Raspberry Pi OS 32-bit | Not a test or support target |
| Raspberry Pi 3 | Insufficient RAM for reliable PyQt5 UI |
| Docker / containerised Raspberry Pi | Not a supported deployment model |
| Raspberry Pi with non-standard display drivers | `khptz doctor` display check not implemented; treat as not validated |

---

## First-pilot validation target

Physical validation is pending on **both** software targets. A validation run
uses one of:

```text
Target A (legacy baseline):
  Hardware:   Raspberry Pi 4 Model B, 2 GB or 4 GB RAM
  OS:         Raspberry Pi OS Bullseye (Debian 11) 64-bit
  Python:     3.9.2 (system apt)

Target B (installation target):
  Hardware:   Raspberry Pi 4 Model B or 5, 4 GB RAM or more
  OS:         Raspberry Pi OS Bookworm (Debian 12) 64-bit, X11 session
  Python:     3.11 (system apt)

Either target:
  PyQt5:      apt package (5.15.x)
  Release:    approved release tag or release-candidate branch
  Profile:    Starter (1 camera) AND Standard (2 cameras) separately
```

The #381 Raspberry Pi MVP validation run and every pilot installation must
record which target was used. Any deviation from this baseline during
validation must be recorded in `docs/MVP_VALIDATION_REPORT.md` as a known
limitation or risk.

---

*See also: `docs/INSTALL_RPI.md`, `docs/DEPENDENCY_PINNING_POLICY.md`, `docs/IMPLEMENTATION_PLAN.md`*
