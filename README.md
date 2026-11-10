# KH PTZ Control

**English** | [Español](#español)

Touchscreen control of VISCA-over-IP PTZ cameras for Kingdom Halls, running on a
Raspberry Pi. The operator taps a seat on a visual layout of the auditorium and the
cameras frame that person, so friends commenting from the audience can be seen on the
hall's displays and on the video stream during the meeting.

Free and open-source (MIT). This is an installable application under active camera
stability work. Automated tests and a successful install do not replace physical validation
of both cameras, saved framing, STOP and recovery on your own equipment. The original application code is
MIT-licensed. Required GUI dependencies and optional components have separate
licences; see [third-party notices](THIRD_PARTY_NOTICES.md) and the
[ATEM dependency gate](docs/ATEM_DEPENDENCY_DECISION.md) before sharing an installed
system or deploying ATEM support.

![KH PTZ Control banner](docs/screenshots/banner.png)

## What it does

- **Visual seat map.** Tap a numbered seat (or a platform position: chairman, lectern,
  reader) and the selected camera moves to the stored preset for that spot.
- **Two cameras.** A "Platform" camera and a "Comments" camera, selected on screen.
- **Presets per seat.** Call mode for live operation; Set mode to store or update the
  framing for any seat in seconds.
- **Session controls.** Meeting schedules and explicit session controls keep normal
  operation separate from setup and shutdown. Check the on-screen session state
  before using camera controls.
- **Operator login.** A simple on-screen password protects the controls; an admin role
  unlocks configuration.
- **ATEM integration (optional).** Camera status can follow the video switcher.
- **Simulation mode.** Fake/demo components support operator UI rehearsal without
  camera hardware; they do not validate a full Raspberry Pi installation.

![Operator panel](docs/screenshots/03-panel.png)

## Safety: STOP is always first

Cameras move; safety is not negotiable. The control path is built so that STOP always
wins:

- A STOP command **queues a pan/tilt stop and a zoom stop together with priority**;
  physical stopping then depends on the camera and the network.
- STOP commands travel in a **priority queue** that bypasses every pending movement.
- If the command queue is full, **new movement commands are dropped — never a STOP**.
- Closing the app or ending a session requests a stop for configured cameras;
  confirm the physical result and use the hall's fallback if the network fails.

## Screenshots

| | |
|---|---|
| ![Operator login](docs/screenshots/02-login.png) | ![Configuration](docs/screenshots/05-config.png) |
| ![First-run setup wizard](docs/screenshots/06-wizard.png) | ![Cameras, VISCA and network discovery](docs/screenshots/08-cameras-atem.png) |
| ![Camera moving: pan/tilt speeds live](docs/screenshots/09-moving.png) | ![STOP: both axes halted, speeds at zero](docs/screenshots/10-stop.png) |
| ![Splash screen](docs/screenshots/01-splash.png) | |

## Requirements

- Raspberry Pi hardware with Raspberry Pi OS. Two software targets, both with
  physical validation required on the target equipment:
  - **Pi 4 or 5 / Bookworm (Debian 12) 64-bit Desktop with Python 3.11** - the installation
    target, rehearsed in a container. Bookworm boots to Wayland by default and the
    GUI requires X11: switch the session with `sudo raspi-config` -> Advanced
    Options -> Wayland -> X11 and reboot before installing. Do not use `--atem` or
    `--dev` on Bookworm (PEP 668 blocks `pip3` there).
  - **Pi 4 / Bullseye (Debian 11) 64-bit with Python 3.9.2** - the legacy baseline,
    still supported. Trixie is not validated.

  See [docs/INSTALL_RPI.md](docs/INSTALL_RPI.md) and
  [docs/RPI_RUNTIME_BASELINE.md](docs/RPI_RUNTIME_BASELINE.md).
- A touchscreen (the UI is designed for touch) and network access to the cameras.
- One or two VISCA-over-IP PTZ cameras (designed for common AV/PTZ heads; not yet
  universally validated across camera models).
- The system Python of the chosen target (3.11 on Bookworm, 3.9.2 on Bullseye;
  other versions are not supported targets) with PyQt5 (installed from `apt` on
  Raspberry Pi OS).

## Install

On a fresh Raspberry Pi OS Bookworm 64-bit Desktop system with an X11 session
(Bullseye remains the legacy baseline; see [Requirements](#requirements)):

```bash
git clone https://github.com/HALCONDEORO/kh-ptz-control.git khptz
cd khptz
bash install_khptz_rpi.sh --guide
```

The guide explains the steps. For the manual readiness check and installation:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER" --check
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

Run this from the Pi desktop as your normal user. `--wizard-user` names that
existing desktop user, not the service account created by the installer.
Run the second command only if readiness passes. For a supervised first installation, use the reviewed, CI-green commit approved
from `main` and record its full SHA; use the signed-off release tag when available.
See [the short hall checklist](docs/INSTALL_TODAY_ES.md). CI passing is not a physical Pi validation result.
Exit 20 means configuration is still required; exit 30 means stop and inspect
the failure. Keep the installer output and never paste passwords into reports.

The installer creates the `khptz` service user, installs dependencies, sets up the
systemd service and the autostart session, and prints the next action: reboot and log into the desktop, or run
`khptz setup` there. The first-run wizard collects camera IPs, seat layout
and login settings. Follow the current wizard prompts; do not use a default password.

The full guide — prerequisites, validation, backup/restore, rollback and
troubleshooting — is [docs/INSTALL_RPI.md](docs/INSTALL_RPI.md).
New to the project? Start with [docs/FOR_KINGDOM_HALLS.md](docs/FOR_KINGDOM_HALLS.md):
equipment targets, a checked installation path and a handover checklist.

### Try it without cameras (simulation mode)

```bash
python3 adapters/sim_mode.py on
```

This legacy helper writes loopback camera addresses into local configuration files
and keeps a backup so `python3 adapters/sim_mode.py off` can restore them. It does
not start the simulator or prove that ATEM and other integrations are isolated.
Use a disposable development checkout, not a live hall configuration. Follow the
[simulation limits and handover checks](docs/FOR_KINGDOM_HALLS.md#training-without-live-equipment).

![Simulation mode: both simulated cameras connected](docs/screenshots/07-simulator.png)

## Camera operation and presets

1. Check the selected camera and session state before recalling a position. Keep
   one controller process connected to each camera. A second app, simulator,
   discovery tool or standalone network probe can displace a persistent VISCA
   connection on single-session camera models.
2. Use **CALL** to recall framing. Use **SET** only when you intend to overwrite
   the camera's saved position, with the required access and confirmation.
   Test each stored position outside a live meeting, with someone watching the
   physical result. See [CALL/SET](docs/CALL_SET_CONTRACT.md).
3. Treat a green connection indicator as transport information. Queue admission
   is not a physical motion confirmation. A timeout or failed save is not success;
   do not repeatedly press SET to make the indicator change.
4. Learn [STOP, STOP ALL and the close options](docs/OPERATOR_GUIDE.md) before
   relying on them. If a camera keeps moving without a network connection, use
   the venue's physical fallback rather than assuming software STOP arrived.

VISCA presets are stored in camera memory. `chairman_presets.json` maps names to
personal preset slots; `room_layout.json` stores the seating layout. A backup of
these files does not copy the physical camera's preset memory. If a map is missing
or corrupt, preserve the data directory and backups before saving new positions:
reusing a slot can overwrite a person's previous framing.

## Update and rollback

Do this outside a live session, with a current backup and an approved target tag
or full commit SHA. Keep the original source checkout: `/opt/khptz` is a deployed
copy, not the place to run `git pull`.

1. Record `khptz version` and `khptz status`. Run `khptz backup`, check that it
   succeeded and retain the resulting ZIP outside the device before changing it.
   Backups can contain private site data; do not attach them to public issues.
2. Close the GUI cleanly. Stop the installed GUI unit: the system service or the
   desktop user's service, according to the installation mode. Do not start both.
3. In the source checkout, fetch and select the approved build, then use the
   [installation wrapper](docs/INSTALL_RPI.md#install-the-runtime-service).
   Preserve the desktop user and GUI mode. Do not update a live system with an
   unreviewed `main` checkout or repair permissions with recursive `chmod`/`chown`.
4. Before reopening the GUI, run `khptz verify-install`. With the GUI stopped,
   run `khptz doctor` and inspect its result. Then rehearse CALL, STOP and recovery
   on both cameras. A software check does not certify physical operation.

For a product install, preview the recorded rollback target first:

```bash
sudo bash /opt/khptz/runtime/installer/rollback.sh --dry-run
```

Only after checking the target, backup and downtime window:

```bash
sudo bash /opt/khptz/runtime/installer/rollback.sh
```

Rollback re-deploys code from the retained source checkout. It is not the same as
restoring a data backup. Use [Update and rollback](docs/UPDATE_ROLLBACK.md) for
explicit `--source` / `--to` targets and GUI-mode details. Do not restore an old
layout or reset the setup wizard merely to undo a code update.

## Camera troubleshooting

Start with the symptom, not a factory reset. Preserve the build SHA, time of the
failure and a short log excerpt. Redact site addresses, names and credentials
before sharing anything publicly.

| Symptom | Checks and next step |
|---|---|
| Camera 1 or 2 flickers between connected and disconnected | Check for another GUI/controller and verify the configured endpoint. Stop the session safely before opening new network probes. Check cable, switch port, camera power and whether the camera accepts only one TCP client. A green badge alone does not prove a completed command. |
| `Connection refused`, empty response or ACK without completion | Refused means the connection was rejected, not that the requested movement completed. Check the endpoint, camera listener and competing controllers. Keep the bytes and timestamps; do not loop reconnects or raise timeouts blindly. |
| A white seat grid or disappearing controls after tapping a seat | Preserve logs and note camera, session state, CALL/SET mode and action. Check for a Python traceback and a simultaneous camera-state change. Do not erase the layout, overwrite presets or run Repair as a guess. |
| GUI missing or dark after desktop login | Check which GUI service owns the window and whether the desktop session is X11. See the [dark-screen checklist](docs/INSTALL_RPI.md#the-gui-never-appears-after-login-dark-screen). Do not start a second GUI to cover a failed one. |
| Address or preset changes disappear after restart | Check whether the UI reported a save failure. Preserve `config.yaml`, any runtime camera override and preset mapping backups. Do not make `/etc/khptz` writable to bypass a failed save. |

A field response can contain a direct-IP ACK followed by an addressed completion,
for example `9041ff` + `a051ff`, or `9042ff` + `a052ff`. Preserve the complete byte
sequence, not just the ACK. These examples are not a rule that any two frames
prove success: address, command socket, terminal error and timeout still matter.
See [camera command results](docs/CAMERA_COMMAND_RESULTS.md).

`khptz verify-install` checks installation state without hardware access.
By contrast, do not run `khptz cameras` or `khptz doctor` alongside a live GUI:
these standalone diagnostics can open additional camera connections. Stop the
GUI first and arrange a safe test window. A support bundle is sanitized, but
review it before sharing; see [support bundle scope](docs/SUPPORT_BUNDLE_CONTRACT.md).

For system GUI installations:

```bash
khptz version
khptz status
sudo systemctl status khptz-control.service --no-pager
journalctl -u khptz-control.service -n 100 --no-pager
```

For a session-owned GUI, run these as its desktop user instead:

```bash
systemctl --user status khptz-gui.service --no-pager
journalctl --user -u khptz-gui.service -n 100 --no-pager
```

Do not post raw logs without checking them for private information. For the
longer checklist, start at [installation troubleshooting](docs/INSTALL_RPI.md).

## Repository map

Keep application code separate from configuration and recorded site data:

| Path | Responsibility |
|---|---|
| `main.py`, `bootstrap.py` | Entry point and dependency wiring |
| `domain/`, `application/` | Models, validation and use cases |
| `ports/`, `adapters/` | Interfaces and their hardware/storage implementations |
| `ptz/visca/` | VISCA framing, parsing, workers and connection ownership |
| `core/` | Event handling, runtime state and supervision |
| `ui/` | PyQt windows, controls and layout rendering |
| `runtime/`, `install_khptz_rpi.sh` | CLI, deployment, systemd and installation checks |
| `config/` | Configuration schema and bundled templates, not live site data |
| `simulation/`, `tests/` | Simulated equipment and regression tests |
| `docs/` | Operator, installation, support and developer guides |

Product installs keep configuration in `/etc/khptz`, runtime data in
`/var/lib/khptz`, logs in `/var/log/khptz` and backups in `/var/backups/khptz`.
Do not move these into the source checkout. See the
[documentation index](docs/DOCS_INDEX.md), [architecture](docs/ARCHITECTURE.md) and
[runtime path contract](docs/RUNTIME_PATH_CONTRACT.md) before reorganizing code.

## Status

Working application, installable MVP candidate. Validate it on your own hardware
before relying on it in a live meeting: run `khptz doctor`, rehearse a session in
simulation mode, and record results in `docs/MVP_VALIDATION_REPORT.md`. See
[docs/ROADMAP.md](docs/ROADMAP.md) for what comes next.

## Contributing

Issues and pull requests are welcome. Please read [AGENTS.md](AGENTS.md) and
[docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) first, and keep the layered architecture
boundaries green (`pytest tests/architecture`).

## License

Original code: MIT, see [LICENSE](LICENSE). Installed dependencies keep their own
terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

<a id="español"></a>

# KH PTZ Control (ES)

Control por pantalla táctil de cámaras PTZ VISCA-over-IP para Salones del Reino, sobre
una Raspberry Pi. El operador toca un asiento en un plano visual del auditorio y las
cámaras encuadran a esa persona, para que los hermanos que comentan desde el público se
vean en las pantallas del salón y en la transmisión durante la reunión.

Libre y de código abierto (MIT). Aplicación instalable en fase activa de trabajo sobre
la estabilidad de las cámaras. Las pruebas automáticas no sustituyen la validación
física de ambas cámaras, los encuadres, STOP y la recuperación en tu equipo. Cualquier salón puede
usar el código original bajo MIT. Las dependencias de interfaz y las opcionales
tienen licencias propias; consulta [los avisos](THIRD_PARTY_NOTICES.md) y el [gate de ATEM](docs/ATEM_DEPENDENCY_DECISION.md) antes de distribuir o
desplegar ese componente.

## Qué hace

- **Plano visual de asientos.** Toca un asiento numerado (o una posición de plataforma:
  presidente, atril, lector) y la cámara seleccionada va al preset guardado.
- **Dos cámaras.** Una de "Plataforma" y otra de "Comentarios", seleccionables en
  pantalla.
- **Presets por asiento.** Modo Call para operar en directo; modo Set para guardar o
  actualizar el encuadre de cualquier asiento en segundos.
- **Sesiones.** El horario y los controles explícitos separan la operación normal de
  la configuración y el cierre. Comprueba el estado de sesión antes de operar.
- **Acceso de operador.** Una contraseña en pantalla protege los controles; un rol de
  administrador desbloquea la configuración.
- **Integración ATEM (opcional).** El estado de las cámaras puede seguir al mezclador.
- **Modo simulación.** Un simulador de cámaras integrado permite ensayar la interfaz de
  operador sin hardware de cámaras; no sustituye la validación física de la Pi.

## Seguridad: STOP siempre primero

Las cámaras se mueven; la seguridad no es negociable. El camino de control está hecho
para que STOP siempre gane:

- Un comando STOP **encola la parada de pan/tilt y la de zoom juntas, con prioridad**;
  la parada física depende después de la cámara y de la red.
- Los STOP viajan en una **cola prioritaria** que adelanta cualquier movimiento
  pendiente.
- Si la cola está llena, **se descartan los nuevos comandos de movimiento — nunca un
  STOP**.
- Al cerrar la aplicación o terminar una sesión se solicita la parada de las
  cámaras configuradas. Confirma el resultado físico y usa la alternativa del
  salón si falla la red.

## Requisitos

- Hardware Raspberry Pi con Raspberry Pi OS. Dos objetivos de software, ambos con
  validación física pendiente:
  - **Pi 4 o 5 / Bookworm (Debian 12) 64 bits con Escritorio y Python 3.11** - el objetivo de
    instalación, ensayado en contenedor. Bookworm arranca en Wayland por defecto y
    la GUI necesita X11: cambia la sesión con `sudo raspi-config` -> Advanced
    Options -> Wayland -> X11 y reinicia antes de instalar. No uses `--atem` ni
    `--dev` en Bookworm (PEP 668 bloquea `pip3`).
  - **Pi 4 / Bullseye (Debian 11) 64 bits con Python 3.9.2** - la base legacy,
    aún soportada. Trixie sigue sin validar.

  Ver [docs/INSTALL_RPI.md](docs/INSTALL_RPI.md) y
  [docs/RPI_RUNTIME_BASELINE.md](docs/RPI_RUNTIME_BASELINE.md).
- Pantalla táctil (la interfaz está pensada para tacto) y red hacia las cámaras.
- Una o dos cámaras PTZ VISCA-over-IP.
- El Python del sistema del objetivo elegido (3.11 en Bookworm, 3.9.2 en Bullseye;
  otras versiones no son objetivos soportados) con PyQt5 (instalado desde `apt` en
  Raspberry Pi OS).

## Instalación

En un sistema Raspberry Pi OS Bookworm de 64 bits con escritorio y sesión X11
recién instalado (Bullseye sigue siendo la base legacy; ver [Requisitos](#requisitos)):

```bash
git clone https://github.com/HALCONDEORO/kh-ptz-control.git khptz
cd khptz
bash install_khptz_rpi.sh --guide
```

Follow the guide / Sigue la guia. Manual check and install / Comprobacion e instalacion manual:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER" --check
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

Ejecuta la orden en el escritorio de la Pi como tu usuario normal.
`--wizard-user` es ese usuario de escritorio ya existente, no la cuenta
de servicio que crea el instalador.
Ejecuta la segunda orden solo si pasa la comprobación previa. Para la primera instalación supervisada, usa el commit revisado y aprobado de
`main`, con CI verde, y anota su SHA completo. Cuando esté disponible usa la
etiqueta aprobada. Consulta la [lista corta para el salón](docs/INSTALL_TODAY_ES.md).
CI en verde no valida una Pi física. El código 20 indica configuración pendiente; el 30 exige parar
y revisar el fallo. Conserva la salida sin incluir contraseñas en los informes.

El instalador crea el usuario de servicio `khptz`, instala dependencias, configura el
servicio systemd y el arranque automático, e indica el siguiente paso: reiniciar e iniciar sesión en el escritorio,
o ejecutar allí `khptz setup`. El asistente recoge las IPs, el plano de asientos
y las opciones de acceso. Sigue sus indicaciones; no uses una contraseña por defecto.

La [lista de instalación en español](docs/INSTALL_RPI_ES.md) cubre preparación,
asistente y entrega.

La guía completa — requisitos, validación, copia de seguridad/restauración, rollback y
resolución de problemas — está en [docs/INSTALL_RPI.md](docs/INSTALL_RPI.md).

### Probar sin cámaras (modo simulación)

```bash
python3 adapters/sim_mode.py on
```

Esta herramienta heredada escribe direcciones de cámara loopback en archivos
locales y guarda una copia para restaurarlas con `python3 adapters/sim_mode.py off`.
No inicia el simulador ni demuestra que ATEM u otras integraciones estén aisladas.
Úsala en un clon de desarrollo desechable, no sobre la configuración de una sala
en uso. Consulta los [límites del ensayo](docs/FOR_KINGDOM_HALLS.md#training-without-live-equipment).

Consulta también las secciones en inglés sobre [cámaras y presets](#camera-operation-and-presets),
[actualización y rollback](#update-and-rollback), [diagnóstico](#camera-troubleshooting)
y [mapa del repositorio](#repository-map).

## Estado

Aplicación funcional, candidata a MVP instalable. Valídala en tu propio hardware antes
de depender de ella en una reunión en directo: ejecuta `khptz doctor`, ensaya una
sesión en modo simulación y registra los resultados en
`docs/MVP_VALIDATION_REPORT.md`.

## Licencia

Código original: MIT, ver [LICENSE](LICENSE). Las dependencias mantienen sus propias
condiciones; consulta [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Read-only installation guide / Guia de instalacion de solo lectura: [GUIDED_INSTALL](docs/GUIDED_INSTALL.md).
