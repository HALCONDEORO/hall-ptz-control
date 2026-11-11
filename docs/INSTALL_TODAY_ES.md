# Primera instalación supervisada: referencia histórica

Esta página conserva el procedimiento de la primera prueba del 10 de noviembre
de 2026. **No es la guía vigente ni autoriza instalar el SHA histórico de abajo.**
Ese código es anterior a las correcciones posteriores de cámaras y STOP.
En la versión actual STOP ALL solo aparece en ADMIN; no interpretar la matriz
histórica de abajo como una descripción del modo USER vigente.
Para instalar o actualizar, sigue [INSTALL_RPI_ES.md](INSTALL_RPI_ES.md) y usa
solo la etiqueta y el SHA que el responsable de la entrega haya aprobado.

Esto prepara una prueba, no certifica el equipo para una reunión. No mover cámaras
ni cambiar el sistema que usa la sala sin permiso del responsable del equipo.

## Antes de salir

- [ ] Clonar la SD completa a un soporte con capacidad suficiente y comprobar que la
  copia puede restaurarse. Guardar aparte la configuración existente. No sobrescribir
  la única SD que funciona. La copia contiene datos privados: mantenerla protegida.
- [ ] Anotar modelo de Pi, sistema y usuario del escritorio. Objetivo: Pi 4/5,
  Raspberry Pi OS Bookworm 64-bit Desktop, Python 3.11, X11. Pi 5 no admite Bullseye;
  Trixie no está validado. No actualizar el SO existente sin plan de recuperación.
- [ ] Si el salón no tiene Internet, preparar dependencias y clon antes, con conexión.
  No añadir `--atem` ni `--dev` en Bookworm. ATEM tiene validación/licencia separadas.

## Versión y comprobación

El SHA histórico que se aprobó para aquella primera prueba fue `20e0deff0355987c9fe458a7d7bc8ebe971afc77`
(merge de la PR #16 en `main`, revisión independiente y CI verde del 2026-11-10).
Los comandos de esta sección se conservan como registro, no como instrucciones
para una nueva instalación. No reutilizar este SHA para la entrega vigente.

```text
# HISTÓRICO: NO EJECUTAR PARA LA ENTREGA VIGENTE
git clone https://github.com/HALCONDEORO/kh-ptz-control.git khptz
cd khptz
git checkout --detach 20e0deff0355987c9fe458a7d7bc8ebe971afc77
git rev-parse HEAD
git status --short
sudo apt update
sudo apt install -y git rsync python3-pyqt5 python3-pyqt5.qtsvg python3-yaml x11-xserver-utils
```

Cambiar Wayland a X11 con `sudo raspi-config` -> Advanced Options -> Wayland ->
X11 y reiniciar si hace falta. Confirmar sesión activa `Type=x11` con `loginctl`.
No borrar archivos desconocidos para dejar limpio el clon: investigar primero.

Desde el escritorio como usuario normal, no desde una sesión root:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER" --check
```

- [ ] Revisar todos los FAIL y avisos, IP únicas y acceso a cámaras. Parar si hay FAIL.
- [ ] Si detecta un `admin.enc` antiguo, parar y seguir `HARDENING2.md`: reset
  privilegiado durante mantenimiento, no copiar contraseñas ni adoptar la de Usuario.

## Instalar y configurar

Solo tras comprobar copia recuperable y aprobar el cambio en este equipo:

```bash
sudo bash install_khptz_rpi.sh --wizard-user "$USER"
```

Modo GUI de sistema predeterminado. El modo GUI de usuario no permite elevación
local a Admin hasta disponer de un broker privilegiado. El cambio de contraseña
Admin desde la GUI está deshabilitado en producción; usar el procedimiento
privilegiado de `HARDENING2.md`. No relajar permisos para hacerlo funcionar.

Código 20: configuración pendiente, no éxito final. Código 30: parar y guardar
diagnóstico. Completar el asistente, reiniciar e iniciar sesión en el escritorio
para actualizar grupos. No usar contraseñas por defecto ni incluirlas en informes.

## Prueba física, antes de depender de él

```bash
khptz version
khptz verify-install
khptz status
khptz doctor
sudo systemctl status khptz-control --no-pager
sudo bash scripts/validate_rpi_deployment.sh --wizard-user "$USER"
```

- [ ] Una sola GUI visible, táctil y acceso Usuario/Admin funcionan como documentado.
- [ ] Cámara correcta por asiento, movimientos y zoom; guardar/recuperar presets de prueba.
- [ ] STOP y STOP ALL detienen físicamente pan/tilt y zoom, incluso con movimientos
  pendientes. Si no paran, usar el control de respaldo de la sala y detener la prueba.
- [ ] Con permiso, interrumpir/restaurar red: la app no se bloquea, muestra el fallo
  y permite recuperación. No confundir un STOP enviado con parada física comprobada.
- [ ] Inicio/final de sesión y ambas opciones de salida, sin acciones inesperadas.
- [ ] Dos reinicios limpios: una sola GUI, configuración y presets conservados.
- [ ] Backup/restauración solo de datos de prueba y recuperación verificadas.
- [ ] Anotar PASS/FAIL/SKIP y SHA en `docs/MVP_VALIDATION_REPORT.md`. Un FAIL no resuelto
  impide usarlo como sistema de reunión; mantener el sistema anterior disponible.

## Si algo falla

Parar, guardar la salida sin secretos y no repetir a ciegas. Para rollback de
aplicación seguir `UPDATE_ROLLBACK.md` con el respaldo comprobado; preservar
`/etc/khptz/secrets` y no ejecutar una reversión de código que deje incompatibles
credenciales/configuración. Si la recuperación no está demostrada, volver al
soporte SD previo verificado con el responsable del equipo. No reformatear ni
borrar la copia original. El ensayo de CI es de contenedor AMD64, no Pi/ARM,
pantalla, systemd real ni cámaras físicas.
