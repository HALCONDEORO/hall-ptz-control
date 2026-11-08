# Fallos de copia: matriz local adicional y limites

`tests/test_installer_copy_failure_recovery.py` ejecuta el bloque real de copia y
su funcion de recuperacion, extraidos de `runtime/installer/install.sh`. Usa
carpetas temporales, un archivo de configuracion sintetico y funciones falsas de
`rsync` y `systemctl`. No necesita root, contenedor, paquetes, camaras ni red.

Esta matriz complementa el ensayo parcial ya existente en
`tests/installer/container_install_test.sh` (rsync fallido, reinicio al abortar y modo GUI
de usuario). No es el primer ensayo ni sustituye el ensayo en contenedor.

El objetivo es comprobar el contrato actual, no certificar la instalacion:

- Si falla la parada del servicio, no empieza la copia.
- Si falla la copia tras cambiar algunos bytes, se conserva el codigo original.
  Se intenta arrancar una vez el servicio que antes estaba activo.
- Si falla ese arranque, el error queda visible y no sustituye el fallo de copia.
- Si antes no estaba activo, no se arranca como efecto de la recuperacion.
- El modo GUI de usuario no arranca la GUI del servicio del sistema al abortar.
- El modo desarrollo no usa `--delete`; si origen y destino coinciden, no copia.
- Un archivo sintetico de configuracion ajeno al arbol de aplicacion no cambia.

## Lo que no prueba

Los codigos de copia 11, 20 y 23 se inyectan: no llenan un disco, no matan un
proceso y no ejecutan rsync real. Los servicios tambien son falsos. El ensayo
termina al acabar la fase de copia; no ejecuta el resto del instalador ni prueba
permisos reales, configuracion, pantalla, reinicio o recuperacion fisica.

Un reinicio del servicio es un intento de recuperar disponibilidad, **no un
rollback atomico**. La prueba deja intencionadamente un archivo parcialmente
actualizado para que no se confunda «se intento arrancar» con «se recupero la
version anterior». No usar este resultado como permiso de instalacion o uso.

Si una copia real falla: conservar el primer error y el codigo, detener el uso y
pedir revision del estado parcial y de la copia de seguridad antes de reintentar,
restaurar o borrar. Ver [la guia humana](INSTALL_HUMANO.md).

Pendiente separado: ensayo desechable del instalador completo con rsync real,
fallo de espacio, interrupcion real y restauracion verificada. Esa prueba necesita
un entorno aislado preparado para ello, no la Pi ni el servidor en uso.
