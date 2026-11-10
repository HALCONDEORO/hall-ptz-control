# Raspberry Pi Golden Image and Provisioning Checklist

Use this checklist to prepare a new Raspberry Pi for KH PTZ Control.
A technician must be able to follow this document on site without guessing.

---

## Hardware requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Model     | Raspberry Pi 4 Model B 4 GB | RPi 4 or 5, 4–8 GB RAM |
| Display   | 1920×1080 HDMI or DSI touchscreen | Official 7" DSI or HDMI touchscreen |
| Storage   | 16 GB microSD (Class 10) | 32 GB+ A2-rated card |
| Network   | Ethernet to camera subnet | Ethernet (not Wi-Fi for VISCA reliability) |

---

## OS and base image

- **OS for new installations**: Raspberry Pi OS Bookworm (Debian 12, 64-bit,
  **Desktop**) with system **Python 3.11** — the installation target, rehearsed
  in a container. Physical validation is still pending; record the first on-site
  run in `docs/MVP_VALIDATION_REPORT.md`.
- **OS, legacy baseline**: Raspberry Pi OS Bullseye (Debian 11, 64-bit) with
  **Python 3.9.2** — still supported for existing installs. Do not mix targets
  on one image. See [Raspberry Pi runtime baseline](RPI_RUNTIME_BASELINE.md).
- **Desktop session must be X11**: Bookworm boots to Wayland by default and the
  GUI units require X11 (`QT_QPA_PLATFORM=xcb`). After the first boot, select
  `sudo raspi-config` -> Advanced Options -> Wayland -> X11 and reboot.
  `runtime/installer/install.sh --check` FAILs while the active desktop session
  is Wayland.
- **User**: record the normal desktop account created for this Pi. Pass that
  account as `--wizard-user`; never use root or the `khptz` service account.
- **Hostname**: `khptz-control` (optional, helps identify on network)

Do **not** bake customer-specific passwords, IPs or names into the base image.
Apply those after provisioning using the configuration steps below.

---

## Phase 1 — OS setup

Run on the freshly flashed Pi:

```bash
# 1. Update system
sudo apt update && sudo apt full-upgrade -y

# 2. Set locale and timezone (adjust for site)
sudo raspi-config nonint do_change_locale en_GB.UTF-8
sudo timedatectl set-timezone Europe/Dublin

# 3. Enable SSH (for support access)
sudo systemctl enable ssh
sudo systemctl start ssh

# 4. Disable screen blanking (always-on display)
sudo raspi-config nonint do_blanking 1
```

On Bookworm, also switch the desktop session to X11 (it defaults to Wayland,
which the GUI units cannot use): `sudo raspi-config` -> Advanced Options ->
Wayland -> X11, then reboot before continuing.

---

## Phase 2 — System dependencies

Install these packages while internet access is available, before taking an
offline image to site:

```bash
sudo apt update
sudo apt install -y git rsync python3-pyqt5 python3-pyqt5.qtsvg python3-yaml x11-xserver-utils
```

Product mode uses system packages; do not install development requirements or
use system pip. Do not add `--atem` or `--dev` on Bookworm/Trixie. An ATEM-enabled
installation needs a separate dependency/licence review; see
[ATEM dependency decision](ATEM_DEPENDENCY_DECISION.md).

---

## Phase 3 — App installation

From the normal desktop account, prepare a clean clone of the approved release:

```bash
git clone https://github.com/HALCONDEORO/kh-ptz-control.git "$HOME/khptz"
cd "$HOME/khptz"
git checkout <approved-tag-or-release-branch>
git remote -v
git status --ignored
sudo bash install_khptz_rpi.sh --wizard-user "$USER" --check
```

The angle-bracket ref is a placeholder: replace it with the approved release.
Do not copy individual scripts or use a source ZIP without `.git`. Keep the
clean source checkout on the Pi: `/opt/khptz` has no Git history and rollback
re-deploys from the original checkout. Remove no customer files to make a
checkout look clean; stop for review if it contains site data or secrets.

After readiness passes and permission for this device is confirmed:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

Exit 20 means configuration is pending, not completion. On exit 30 or an
unexpected failure, keep the first error and stop for review before retrying.
Reboot and log into the desktop so new group membership takes effect.

---

## Phase 4 — Customer configuration

Keep the reusable base image **unprovisioned**. Configure the individual Pi
through the on-device setup wizard, not by writing legacy IP/password files:

```bash
khptz setup
```

Confirm room details, actual camera IPs and VISCA IDs, camera count/roles and
optional ATEM settings. Two-camera rooms need **Add camera**. Operator and
administrator passwords must differ; enter them only in the wizard. Do not
commit them or copy credential files by hand.

The service deliberately waits for `/etc/khptz/.provisioned`. It is normal for
it not to run before the wizard completes. If the Pi is already provisioned,
do not force the wizard or delete that marker to fix a startup problem.
See [installation guide](INSTALL_RPI.md) for the authenticated repair flow.

---

## Phase 5 — Product directory structure

```text
/home/<desktop-user>/khptz/  clean source checkout, retained for rollback
/opt/khptz/                 deployed app code, not a Git checkout
/etc/khptz/                 site config and provisioning marker
/var/lib/khptz/             persistent runtime data
/var/log/khptz/             logs
/var/backups/khptz/         local backup ZIPs
/etc/systemd/system/khptz-control.service
```

The installer manages ownership and permissions. Do not recursively `chown`
the product tree to the desktop user or copy secrets into the source checkout.
See [runtime path contract](RUNTIME_PATH_CONTRACT.md).

---

## Phase 6 — First boot verification

After the wizard completes:

```bash
khptz version
khptz verify-install
khptz status
khptz doctor
sudo systemctl status khptz-control --no-pager
journalctl -u khptz-control -n 50 --no-pager
sudo bash scripts/validate_rpi_deployment.sh --wizard-user "$USER"
```

The validator writes a timestamped report. Run it after each of two clean
reboots; keep the reports and resolve every FAIL before handover. Development
unit tests are not a substitute for this physical check and are not a required
product dependency.

Confirm on screen, with permission to move the cameras:
- [ ] Exactly one GUI starts after desktop login, without a restart loop.
- [ ] The touchscreen responds and the operator password works.
- [ ] The configured camera count/roles and actual cameras match.
- [ ] Camera movement, presets, STOP and session start/end work physically.
- [ ] The active desktop session is X11: use `loginctl list-sessions`, then
  `loginctl show-session SESSION_ID -p Name -p Active -p Type` for the recorded
  desktop user. Require `Active=yes` and `Type=x11`; do not assume the first
  `seat0` row is active. Re-check after OS upgrades.
- [ ] Create a backup with `khptz backup`, record its path and retain it under
  the site's approved handling rules. Test restore only on non-customer data.
- [ ] Record the approved version, results and accepted limitations in
  `docs/MVP_VALIDATION_REPORT.md`. Until physical checks pass, do not claim
  customer/pilot readiness.

---

## What must NOT be in the golden image

- Customer passwords or `password.enc`
- Customer camera IPs or VISCA IDs
- Customer preset maps (`chairman_presets.json`, `seat_names.json`)
- Any private keys or certificates
- ATEM credentials

Apply all customer-specific data after cloning/flashing using Phase 4.

---

## Cloning an existing good image

Prepare reusable cards only from a clean, unprovisioned base image with the
approved dependencies and source checkout already present. Keep the original
card intact until the replacement has been verified.

Do not clone an already provisioned customer card for another site and assume
that removing legacy files sanitizes it: config, runtime data, protected
credentials, logs and backups live outside the source checkout. Cross-site
sanitization needs a separately reviewed process. For recovery of the same
site, follow the permission, backup and restore gates in
[update and rollback](UPDATE_ROLLBACK.md).

---

## Related documents

- `docs/INSTALL_RPI.md` — full end-to-end Raspberry Pi installation guide
- `docs/UPDATE_ROLLBACK.md` — update and rollback procedure
- `docs/RELEASE_CHECKLIST.md` — release gate checklist before customer deployments
- `docs/SOAK_TEST.md` — real-world soak test after deployment
- `runtime/installer/install.sh` — automated installer script
- `runtime/installer/rollback.sh` — safe rollback script
- `runtime/systemd/khptz-control.service` — systemd service template
