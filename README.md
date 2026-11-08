# KH PTZ Control

**English** | [Español](#español)

Touchscreen control of VISCA-over-IP PTZ cameras for Kingdom Halls, running on a
Raspberry Pi. The operator taps a seat on a visual layout of the auditorium and the
cameras frame that person, so friends commenting from the audience can be seen on the
hall's displays and on the video stream during the meeting.

Free and open-source (MIT). Built for a real hall and tested in live meetings; the
Raspberry Pi installation is still pending. The original application code is
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
- **Session awareness.** The app knows the meeting schedule and arms itself for the
  session; operators just log in and serve.
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

- Raspberry Pi hardware with Raspberry Pi OS. The software and CI baseline is
  **Raspberry Pi OS Bullseye (Debian 11), 64-bit, with Python 3.9.2**. This is a
  software baseline: no hardware has been validated yet. Two paths:
  - **Pi 4 / Bullseye** - the path the docs, installer and CI target.
  - **Pi 5 / Bookworm or Trixie** - untested. Raspberry Pi 5 does not run Bullseye. Bookworm and Trixie default to Wayland, so the
    session must be switched to X11 first, and `--atem` and `--dev` must not be used
    there. See the [Raspberry Pi 5 product page](https://www.raspberrypi.com/products/raspberry-pi-5/) for its supported OS releases.

  See [docs/INSTALL_RPI.md](docs/INSTALL_RPI.md) and
  [docs/RPI_RUNTIME_BASELINE.md](docs/RPI_RUNTIME_BASELINE.md).
- A touchscreen (the UI is designed for touch) and network access to the cameras.
- One or two VISCA-over-IP PTZ cameras (designed for common AV/PTZ heads; not yet
  validated on real cameras).
- Python 3.9.2 (the system Python on Bullseye; newer versions are not validated) with PyQt5
  (installed from `apt` on Raspberry Pi OS).

## Install

On a fresh Raspberry Pi OS Bullseye system (the Pi 5 path is untested, see [Requirements](#requirements)):

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

Run this from the Pi desktop as your normal user. `--wizard-user` names that
existing desktop user, not the service account created by the installer.
Run the second command only if readiness passes. For a pilot, first check out
the approved tag; `main` and CI passing are not a physical Pi validation result.
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

Libre y de código abierto (MIT). Construido para un salón real y probado en reuniones
en directo; la instalación en la Raspberry Pi aún está pendiente. Cualquier salón puede
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
- **Sesiones.** La aplicación conoce el horario de las reuniones y se prepara para cada
  sesión; el operador solo inicia sesión y sirve.
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

- Hardware Raspberry Pi con Raspberry Pi OS. La base de software y CI es
  **Raspberry Pi OS Bullseye (Debian 11), 64 bits, con Python 3.9.2**. Es una base de
  software: aún no se ha validado ningún hardware. Dos caminos:
  - **Pi 4 / Bullseye** - el camino al que apuntan la documentación, el instalador y CI.
  - **Pi 5 / Bookworm o Trixie** - pendiente de prueba. La Pi 5 no funciona con Bullseye. Bookworm y Trixie usan Wayland por
    defecto: hay que cambiar la sesión a X11 antes y no usar `--atem` ni `--dev` ahí.
    Consulta la [ficha de la Raspberry Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/) para ver sus sistemas soportados.

  Ver [docs/INSTALL_RPI.md](docs/INSTALL_RPI.md) y
  [docs/RPI_RUNTIME_BASELINE.md](docs/RPI_RUNTIME_BASELINE.md).
- Pantalla táctil (la interfaz está pensada para tacto) y red hacia las cámaras.
- Una o dos cámaras PTZ VISCA-over-IP.
- Python 3.9.2 (el Python del sistema en Bullseye; versiones nuevas no validadas) con PyQt5
  (instalado desde `apt` en Raspberry Pi OS).

## Instalación

En un sistema Raspberry Pi OS Bullseye recién instalado (el camino Pi 5 está sin probar, ver [Requisitos](#requisitos)):

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
Ejecuta la segunda orden solo si pasa la comprobación previa. Para una prueba
piloto, selecciona primero la etiqueta aprobada: `main` y CI en verde no validan
una Pi física. El código 20 indica configuración pendiente; el 30 exige parar
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

## Estado

Aplicación funcional, candidata a MVP instalable. Valídala en tu propio hardware antes
de depender de ella en una reunión en directo: ejecuta `khptz doctor`, ensaya una
sesión en modo simulación y registra los resultados en
`docs/MVP_VALIDATION_REPORT.md`.

## Licencia

Código original: MIT, ver [LICENSE](LICENSE). Las dependencias mantienen sus propias
condiciones; consulta [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Read-only installation guide / Guia de instalacion de solo lectura: [GUIDED_INSTALL](docs/GUIDED_INSTALL.md).
