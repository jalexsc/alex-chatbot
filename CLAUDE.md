# Instrucciones para Claude

Repositorio con dos proyectos:
- `alex-chatbot/` — chatbot de consulta del catálogo FOLIO (piloto).
- `biblioselect/` — **LibriNova**, plataforma de selección y adquisición bibliográfica.

## Cambios en LibriNova: ir directo al módulo

1. Las peticiones llegan con un ID de módulo: `[M3] …`. Si no lo traen, identifícalo en
   `biblioselect/docs/MODULOS.md` y dilo en la respuesta.
2. Lee **solo**: la fila del módulo en `MODULOS.md`, su sección `§4 M#` y `§2 Reglas globales`
   de `biblioselect/docs/PROMPT_MAESTRO.md`, y los archivos de la columna «Código».
   No leas el prompt maestro completo ni explores el repositorio entero.
3. Implementa, ejecuta las pruebas (`python -m pytest -q` en `biblioselect/backend`) y prueba la
   interfaz si el cambio la afecta.
4. Actualiza en `MODULOS.md` el estado, los archivos y el registro de cambios del módulo.

## Reglas que no se negocian

- Autorización siempre en el servidor. Nadie aprueba su propia solicitud.
- Nunca guardar, mostrar ni registrar secretos. Credenciales de FOLIO solo en el backend.
- Integraciones no disponibles: adaptador `Fake…` marcado, nunca datos ficticios presentados como reales.
- Operaciones financieras o irreversibles en FOLIO: solo con confirmación humana.
