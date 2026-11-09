# Instalación en Raspberry Pi: lista de trabajo y entrega

Esta guía resume el flujo en español. La referencia detallada es
[INSTALL_RPI.md](INSTALL_RPI.md). No autoriza un despliegue: hacen falta permiso
para el equipo concreto y una versión aprobada. No hay un PASS de hardware por
el hecho de que CI esté en verde.

## Antes de tocar el equipo

- Anota modelo de Pi, sistema, Python, etiqueta/commit y usuario de escritorio.
- El objetivo de la instalación es Raspberry Pi OS Bookworm de 64 bits con
  escritorio y Python 3.11. El ensayo de instalación en contenedor Bookworm
  pasó; no equivale a validación física de Pi, X11, pantalla ni cámaras.
- Bookworm y Trixie arrancan en Wayland (wayfire/labwc) por defecto y las
  unidades de la GUI solo funcionan con X11 (DISPLAY=:0, xhost). Cambia la
  sesión a X11 (`sudo raspi-config` -> Advanced Options -> Wayland -> X11) y
  reinicia en el escritorio ANTES de instalar. La comprobación `--check`
  falla si detecta una sesión Wayland activa; sin sesión visible, avisa.
- El modelo de Pi y el sistema instalado se comprueban en el equipo antes de
  decidir cambios. La Pi 5 no funciona con Bullseye. Trixie sigue sin validar.
  Usa el modo GUI de sistema predeterminado; el modo GUI de usuario no está
  aprobado para autenticación local. No añadas `--atem` ni `--dev` sin su
  comprobación específica.
- Verifica red, IP únicas y cámaras previstas. No muevas cámaras sin permiso.
- En una actualización, confirma una copia recuperable y el plan de rollback.
  Si falla la copia, para antes de cambiar datos.
- Si la versión detecta credenciales antiguas que requieren migración, usa su
  procedimiento privilegiado revisado. No copies ni borres archivos de
  contraseña para forzar acceso.

## Preparar y comprobar

En el escritorio, como usuario normal, desde un clon de la etiqueta aprobada:

```bash
sudo apt update
sudo apt install -y git rsync python3-pyqt5 python3-pyqt5.qtsvg python3-yaml x11-xserver-utils
sudo bash install_khptz_rpi.sh --wizard-user "$USER" --check
```

`$USER` es la persona que inicia sesión en el escritorio, no `root` ni la cuenta
`khptz` del servicio. No continúes con fallos de requisitos. Conserva la salida
sin contraseñas ni otros secretos.

## Instalar y configurar

Solo tras pasar la comprobación y con permiso para esta instalación:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

- Código 0: instalado según las comprobaciones del instalador, con posibles avisos.
- Código 20: falta configurar. No equivale a una instalación terminada.
- Código 30: fallo. Conserva el diagnóstico y para antes de repetir.

Reinicia e inicia sesión para actualizar los grupos del usuario. Completa el
asistente con los datos de la sala. Sigue sus indicaciones y no uses una
contraseña por defecto. Antes de terminar el asistente es normal que el servicio
esté bloqueado por falta de `/etc/khptz/.provisioned`.

ATEM es opcional. Su paquete publicado tiene licencia GPL; un pin no aprueba su
distribución ni demuestra compatibilidad física. Revisa
[ATEM_DEPENDENCY_DECISION.md](ATEM_DEPENDENCY_DECISION.md) antes de añadirlo.

## Verificar después del asistente

```bash
khptz version
khptz verify-install
khptz status
khptz doctor
sudo systemctl status khptz-control --no-pager
```

En modo GUI de usuario, comprueba `systemctl --user status khptz-gui.service`
desde el escritorio. No actives los dos servicios GUI a la vez. La elevación de
administrador en GUI-user puede estar cerrada hasta disponer del broker
privilegiado; consulta las notas de la versión.

Con permiso en el equipo de prueba, registra dos reinicios limpios, una sola GUI,
respuesta táctil, cámaras, presets y comienzo/final de sesión. Comprueba backup,
restauración solo con datos de prueba y rollback antes de una entrega real.

```bash
sudo bash scripts/validate_rpi_deployment.sh --wizard-user "$USER"
```

Este validador no modifica configuración ni servicios, pero crea un directorio
y un informe con fecha y puede generar logs de diagnóstico. Revisa el informe:
no entregues el sistema con FAIL sin resolver. Guarda evidencia en
`MVP_VALIDATION_REPORT.md`, incluyendo limitaciones aceptadas. Una guía revisada
no sustituye esa prueba física.
