# KH PTZ Control for Kingdom Halls

KH PTZ Control is a free, open-source touchscreen application for operating
VISCA-over-IP PTZ cameras from a visual seating layout. The original application
code is MIT-licensed; required GUI and optional ATEM components have their own
terms. Read [third-party notices](../THIRD_PARTY_NOTICES.md) before sharing a
preinstalled Pi or reusable image.

The app has been used in live meetings at its original hall. That is not a
validation of a Raspberry Pi installation at another hall. The repository is an
installable MVP candidate, not a hardware-certified appliance release.

## Plan the installation

| Item | Current software target or required check |
|---|---|
| Pi | Pi 4, 2 GB minimum, 4 GB preferred; physical validation remains required. |
| OS | Raspberry Pi OS Bookworm 64-bit Desktop, Python 3.11, X11 (the Bullseye 64-bit / Python 3.9.2 baseline remains supported on Pi 4). Bookworm defaults to Wayland: switch the session to X11 before installing. |
| Pi 5 | Bookworm 64-bit only — it cannot boot Bullseye. Trixie remains unvalidated. |
| Display | Target 1920x1080 touchscreen; test touch mapping and readability on the actual display. |
| Cameras | One or two compatible VISCA-over-IP cameras; verify model, transport and configured port rather than assuming every VISCA camera works. |
| Network | Prefer wired LAN, unique reserved/static addresses and no public exposure of camera controls. |
| Storage | Minimum target 16 GB microSD; preserve a recoverable backup on separate media. |
| ATEM | Optional, with separate licence, dependency and model/firmware validation gates. |

Confirm permission for the specific equipment and a time when camera movement
will not disrupt a meeting. Assign a local person responsible for installation,
operator training, backups and recovery. Do not copy another hall's passwords,
seat names or network settings.

## Check, then install

Use an approved tag or release-candidate revision, not an arbitrary current
`main`. The detailed [installation guide](INSTALL_RPI.md) covers prerequisites,
updates and rollback; the [Spanish checklist](INSTALL_RPI_ES.md) covers handover.
From that checkout, in the Pi's desktop session as its normal user:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER" --check
```

Install only after resolving readiness failures:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

`--wizard-user` names the existing desktop user, not `root` or the service user.
Exit 20 means configuration is still required; exit 30 means stop and inspect the
failure. Read the printed next action: a reboot/login or `khptz setup` may be
needed. The wizard is not guaranteed to open immediately from the installer.
Use the wizard's current password prompts; do not rely on a default password.

After setup, run `khptz version`, `khptz verify-install`, `khptz status` and
`khptz doctor`. A successful software check does not replace hardware rehearsal.
Do not install or change credentials during a live meeting.

## Training without live equipment

The project has fake/demo components for development and training, but a mode
name alone is not proof of network isolation. Use a disposable configuration,
keep real camera/ATEM addresses and site data out of it, and disconnect test
systems from live AV equipment before rehearsal.

The legacy `python3 adapters/sim_mode.py on` helper changes local camera address
files to loopback and saves a backup. It does **not** launch a simulator or
isolate every integration. Restore with `off` only in the same disposable
checkout and verify the resulting configuration. Do not run it on production
configuration as a shortcut to safe training.

## Handover before a live meeting

Record the exact revision, Pi/OS/Python versions and any accepted limitations in
[MVP_VALIDATION_REPORT.md](MVP_VALIDATION_REPORT.md). With permission to move the
real equipment, rehearse login, seat selection, presets, STOP, session end and
recovery using the [operator guide](OPERATOR_GUIDE.md). Confirm physical camera
response: a queued command or a green indicator is not proof of a stopped camera.

Before handover, also verify:

- Two clean reboots, one GUI instance and the intended desktop/service startup.
- Touchscreen input, camera selection and actual framing for this hall's layout.
- A recoverable backup, a restore using test data and the rollback procedure.
- Local ownership of credentials, backups, updates and operator training.
- A fallback way to run the meeting if the Pi, network or camera is unavailable.

Do not mark unperformed checks PASS. Report faults through repository Issues
only after removing site data, names, addresses and secrets from the evidence.

## Privacy and licence boundaries

Optional seat names can identify people. Prefer seat labels where names are not
needed. Keep backups and exported support bundles private and inspect them
before sharing; local storage does not make an export anonymous. See
[privacy notes](PRIVACY_NOTES.md) for the data and handover questions.

The source licence permits use and adaptation; installed dependencies retain
separate obligations. Preserve [LICENSE](../LICENSE) and upstream notices. This
guide neither changes copyright ownership nor approves redistribution of a
complete installed image.
