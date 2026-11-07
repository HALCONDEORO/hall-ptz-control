# On-device setup wizard

The setup wizard is the **on-device, touchscreen first-run experience** that runs
on the Raspberry Pi itself. It replaces console-based setup: an operator taps
through a few pre-filled screens to write the installation configuration. A
successful provisioning result does not prove the GUI is running or the hardware
is ready. Check runtime diagnostics before handover.

It is **not** a Windows tool and does not run off-device. Everything happens on
the Pi's own desktop session.

---

## Entry point

```bash
khptz setup            # open the wizard (fresh install)
khptz setup --force    # Repair: reopen on an already-provisioned install
```

`khptz setup` is **idempotent**. On a product install using `/etc/khptz`,
it prints a note and exits `0` **without** opening a window only when both
`.provisioned` and `.rpi-integrated` exist. If `.provisioned` exists but
`.rpi-integrated` is missing, it opens the wizard for integration migration.
With an overridden configuration directory (tests/development), only the
provisioned marker is required to suppress the window.

| Situation | `khptz setup` | `khptz setup --force` |
|---|---|---|
| Not provisioned (fresh) | Opens the wizard | Opens the wizard |
| Product: provisioned, integration marker missing | Opens for integration migration | Opens in **Repair** mode |
| Product: both markers present | Exits 0, no window | Opens in **Repair** mode |
| Overridden config directory: provisioned | Exits 0, no window | Opens in **Repair** mode |

Source: [`runtime/cli.py`](../runtime/cli.py) (`cmd_setup`) →
[`runtime/setup_launcher.py`](../runtime/setup_launcher.py)
(`setup_wizard_needed` guard + `run_setup_wizard`).

---

## First-boot autostart

Use the supported top-level wrapper from the normal desktop account, not a root
login. `$USER` must name that desktop account, never the `khptz` service account:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

The wrapper runs readiness checks and invokes the product installer. Exit `20`
means configuration is still required; exit `30` means failure. Reboot and log
back into the desktop so new group membership takes effect, then complete setup.
See [Raspberry Pi installation](INSTALL_RPI.md#install-the-runtime-service) for
release and OS gates, options and recovery. Do not bypass the wrapper by invoking
`runtime/installer/install.sh` directly.

The product installer installs two separate launchers so the wizard appears
automatically on first desktop login **and** the menu entry can still open
Repair afterwards:

- `runtime/khptz-setup-menu.desktop` (`Exec=khptz setup --force`) →
  `/usr/share/applications/khptz-setup.desktop` (applications menu), and
- `runtime/khptz-setup.desktop` (`Exec=khptz setup`, no `--force`) dropped into
  the desktop (wizard) user's `~/.config/autostart/khptz-setup.desktop` (XDG
  autostart on login).

The autostart entry fires on every desktop login. On a product install it
suppresses the wizard only once both `.provisioned` and `.rpi-integrated` exist;
a missing integration marker opens the migration wizard even if the room is
already provisioned. The menu entry always passes `--force`, so clicking it
after setup reopens Repair rather than doing nothing.

The desktop (wizard) user defaults to `$SUDO_USER`; override with
`--wizard-user <user>`.

---

## Repair mode

`khptz setup --force` on a provisioned install opens the wizard **pre-filled with
the current configuration** (site, contact, cameras, ATEM, network profile), read
from the installed `config.yaml`. The operator edits values in place instead of
re-entering everything.

Passwords are **not** recoverable from the encrypted secrets, so they are left
blank and must be re-confirmed on the Passwords screen.

If `config.yaml` exists but fails to load, the wizard refuses to open at all
rather than proceeding with generic defaults that a save would silently write
over the real cameras/ATEM/network settings — `khptz doctor` is the next step.

Source: `ProvisioningService.answers_from_settings` / `load_existing_answers`
in [`application/provisioning_service.py`](../application/provisioning_service.py).

### Admin sign-in gate

Reopening Repair on an already-provisioned install requires the **current
administrator password** first (an `AdminAuthPage` shown as the wizard's first
screen). Without it, desktop-session access to the wizard user alone would be
enough to reconfigure cameras/network or reset both passwords.

That page only *collects* the password — it does not verify it. The wizard
runs unprivileged in the desktop session and cannot reliably decrypt the
`khptz:khptz`-owned admin secret itself. Verification happens in the
**privileged** provisioning oneshot (`runtime/provision.py::run_provision`),
which checks it via `application.authentication.verify_admin` before applying
anything, whenever `.provisioned` already exists. This also closes the more
direct bypass: since `/run/khptz` is writable by the wizard user, a raw request
dropped there — skipping the wizard UI entirely — would otherwise apply
without ever proving the admin password.

A wrong password surfaces as a failure on the Installing page (via the same
`issues` mechanism as any other validation failure), not immediately on the
sign-in screen.

---

## How provisioning actually happens (privilege split)

The wizard runs **unprivileged** in the desktop session — it never needs root and
never writes `/etc/khptz` directly. Instead:

```text
wizard (desktop user)
  └─ writes request → /run/khptz/request.json   (tmpfs, 0750 <wizard-user>:root)
       └─ khptz-provision.path (systemd) reacts
            └─ runtime/provision.py (root oneshot):
                 validate → snapshot → apply config.yaml + secrets + OS steps
                 → write .provisioned marker → write result.json → shred request
```

The single `sudo` step is running the installer once; after that the wizard
provisions with **no further password prompt** via this channel.

- Request/result contract: [`application/provision_handoff.py`](../application/provision_handoff.py)
- Privileged entry point: [`runtime/provision.py`](../runtime/provision.py)
- Channel units: `runtime/systemd/khptz-provision.{service,path}`

### Rollback safety

Before applying, the privileged step snapshots `config.yaml` and both secrets.
If apply fails mid-flow, it attempts to restore the previous files (repair) or
remove partial writes (fresh install). Restoration is best-effort. When rollback
returns normally, the failure result includes `rolled_back`; that flag does not
certify complete restoration. It can be `true` even if a file could not be
recreated, because the file-write helper can return without writing. If rollback
raises, the outer error result can omit `rolled_back` entirely. Verify the files
and runtime state after a failure before retrying or handing over the install.
This is not a rollback of every OS change or a guarantee that a failed run leaves
no partial state. See `ConfigSnapshot`, `_safe_write_regular_file` and
`run_provision` in [`runtime/provision.py`](../runtime/provision.py).

---

## Screens

Welcome → Device check → Room details → Cameras → Optional (ATEM + network) →
Passwords (operator + administrator) → Review → Installing → Done.

- **Device check** gates Next while any preflight check is blocking.
- **Review** gates Finish while validation issues remain (nothing is written
  until confirmed).
- **Installing** drops the request and polls the result with a timer — the
  touchscreen stays responsive and Next stays disabled until provisioning
  succeeds.
- **Done** checks the provisioned marker and configuration file. On a product
  Pi it also checks the integration marker and the selected launcher files
  (system or desktop-session mode). It points to `khptz doctor` if those checks
  fail. File-presence checks do not prove the process is running or cameras
  respond.

Pages collect input only; all file writes go through `ProvisioningService`
(headless, Qt-free). Source: [`ui/setup_wizard/`](../ui/setup_wizard/). The
branded touchscreen look is applied once via `setup_wizard_qss()` in
[`ui/styles.py`](../ui/styles.py).

---

## Check runtime state after setup

Run `khptz verify-install`, `khptz status` and `khptz doctor` before handover.
In default system GUI mode, provisioning attempts to restart
`khptz-control.service`, but that restart is best-effort: it can fail without
changing the successful provisioning result. In `--gui-mode user`, provisioning
does not restart the system GUI service; the desktop session owns
`khptz-gui.service` instead. Check the service for the installed mode:

```bash
# Default system GUI mode:
sudo systemctl status khptz-control --no-pager
# Desktop-session GUI mode, as the desktop user (without sudo):
systemctl --user status khptz-gui --no-pager
```

The current Done screen's "Installed and running" wording is not a live process
check. Confirm runtime state, display access and real camera behavior separately.
Source: `_restart_control_service` in
[`runtime/provision.py`](../runtime/provision.py),
[`application/install_verification.py`](../application/install_verification.py),
and the [installation guide](INSTALL_RPI.md#systemd-autostart-validation).

---

## Validation status

Software-complete and unit-tested offscreen. **Real Raspberry Pi hardware QA is
still required** (#381): confirm the autostart fires in the desktop session, the
`/run/khptz` channel converges, permissions are correct on real hardware, and the
touchscreen render is legible with the installed fonts.
