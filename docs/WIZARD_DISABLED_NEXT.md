# Boton Next deshabilitado

El estilo del asistente aplicaba el gradiente verde a un boton por defecto aun
estando deshabilitado. Este cambio solo añade una regla QSS mas especifica para
el estado deshabilitado: fondo gris claro, texto gris legible y borde visible.
No cambia validaciones, navegacion, permisos, provision ni logica del boton.
Los botones activos conservan su gradiente verde.

Pruebas Qt reales a800x480 y1280x720 fuerzan Next como boton por defecto,
comprueban el pixel pintado, verifican que un clic deshabilitado no avanza y
que el exito simulado recupera el estilo verde. Fallan sobre la regla anterior.
No es una prueba en pantalla fisica ni provision real.

Las capturas aisladas muestran el texto heredado de mainb847e5b. La correccion
del consejo de reintento tras timeout es un cambio separado (0010), no parte
de esta correccion de estilo.
