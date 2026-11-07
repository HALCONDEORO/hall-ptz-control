# Antes de tocar la Pi

En el escritorio de la Pi, desde el clon revisado, ejecuta como usuario normal:

```bash
/usr/bin/python3 -B scripts/site_preflight.py
```

Solo lee: modelo, OS, arquitectura, Python, sesión, dependencias y discos.
No necesita sudo, no instala nada, no mueve cámaras, no lee contraseñas y no
conecta con dispositivos de red. Copia la salida sin añadir credenciales.
Devuelve 20 deliberadamente: inventario completado no equivale a permiso para
instalar ni a compatibilidad probada. `unknown` significa no comprobado.

- Identifica la SD original y el pendrive por tamaño/ruta/modelo; nunca adivines
  que `/dev/sda` es el destino. No formatees ningún disco.
- Confirma espacio y sistema de archivos del pendrive antes de guardar una imagen.
- La imagen completa se obtiene con la Pi apagada limpiamente, desde otro Linux
  con lector y todas las particiones de la SD desmontadas. Una copia del sistema
  en marcha puede ser incoherente.
- Verifica integridad de la imagen y comparación completa contra la SD original.
  Una suma del archivo sola no demuestra que sea igual a la SD.
- Sin copia verificada no se instala sobre la SD original. Alternativa: otra SD,
  dejando intacta y guardada la original.
- El objetivo Bookworm64/Python3.11 requiere X11 y modo GUI de sistema; el ensayo
  de contenedor no demuestra Pi, pantalla, red ni cámaras reales.
- Usa la guía de instalación revisada después de resolver esos puntos. Este
  inventario no elimina ninguna comprobación del instalador ni autoriza cambios.
