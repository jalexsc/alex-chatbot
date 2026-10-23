# Mapa de módulos — LibriNova

Índice para dirigir cada cambio al módulo correcto y leer solo lo necesario.
Especificación completa: [`PROMPT_MAESTRO.md`](PROMPT_MAESTRO.md) (leer solo la sección indicada).

> El código vive en `biblioselect/backend/` (nombre provisional anterior a LibriNova).
> Rutas abreviadas abajo: `app/` = `biblioselect/backend/app/`, `tests/` = `biblioselect/backend/tests/`.

## Cómo pedir un cambio

```
[M3] Agregar alerta ámbar al 80 % del plazo en la bandeja.
Aceptación: una solicitud con 4 de 5 días en evaluación se ve en ámbar.
No tocar: M1.
```

Con eso, Claude:
1. Lee la fila del módulo en este mapa y su sección `§4 M#` del prompt maestro.
2. Abre solo los archivos de la columna **Código** y sus pruebas.
3. Implementa, prueba y actualiza la columna **Estado** de este mapa.

Si el cambio cruza módulos, nómbralos todos: `[M3+M10] Recordatorio por plazo vencido.`

## Índice

| ID | Módulo | Estado | Código | Pruebas |
|---|---|---|---|---|
| M0 | Plataforma y configuración | 🟡 MVP | `app/main.py` (`create_app`, `health`, `domain_error_handler`), `app/errors.py`, `backend/requirements.txt` | — |
| M1 | Solicitudes (formulario y CRUD) | 🟡 MVP (sin adjuntos) | `app/schemas.py` (`RequestIn`), `app/identifiers.py`, `app/service.py` (`create_request`, `update_request`, `cancel_request`), `app/db.py` (`BibliographicRequest`), rutas `/api/requests*` en `app/main.py` | `tests/test_identifiers.py`, `tests/test_api.py` |
| M2 | Bandeja y evaluación | 🟡 Solo transiciones | `app/service.py` (`list_requests`), `app/workflow.py` (`start_review`, `request_info`, `send_to_approval`, `reject_library`) | `tests/test_api.py` |
| M3 | Workflow y reloj de días | 🟡 Workflow y reloj hechos · ⚪ plazos editables desde la app, alertas (M10) | `app/workflow.py` (`Status`, `TRANSITIONS`), `app/clock.py` (`ClockSettings`, `compute_clock`, `segments`, `DEFAULT_SLA_DAYS`), `app/service.py` (`apply_transition`, `available_actions`, `_record`, `clocks_for`), `app/db.py` (`WorkflowEntry`), `app/main.py` (`present`, `_serialize_clock`, `_serialize_history`) | `tests/test_clock.py`, `tests/test_api.py` |
| M4 | Aprobaciones y fondos | 🟡 Transiciones · ⚪ fondos | `app/workflow.py` (`approve_program`, `approve_budget`), `app/service.py` (`_can_execute`) | `tests/test_api.py` |
| M5 | Adquisiciones | ⚪ Pendiente (solo `complete_acquisition`) | — | — |
| M6 | Conector FOLIO | ⚪ Pendiente en LibriNova | Reutilizable: `folio_login_module.py` (raíz), `alex-chatbot/backend/sources/folio.py` (lectura de inventario) | — |
| M7 | Conectores externos | ⚪ Pendiente | — | — |
| M8 | Auditoría | 🟡 MVP | `app/service.py` (`audit`), `app/db.py` (`AuditLog`), ruta `/api/audit` en `app/main.py` | `tests/test_api.py` |
| M9 | Usuarios y roles | 🟡 Auth de desarrollo | `app/db.py` (`User`, `UserRole`), `app/main.py` (`current_user`, `require_roles`, `/api/admin/users`), `app/seed.py`, `app/workflow.py` (`Role`) | `tests/test_api.py` |
| M10 | Notificaciones | ⚪ Pendiente | — | — |
| M11 | Agente IA y MCP | ⚪ Pendiente | Referencia: `alex-chatbot/backend/agent.py` (bucle de tools) | — |
| M12 | Dashboard e informes | ⚪ Pendiente | — | — |
| M13 | Interfaz y diseño | 🟡 Página única con reloj | `app/static/index.html` (`clockBadge`) | Manual (navegador o Playwright) |
| M13·nube | Prototipo en la nube de Claude | 🟡 Publicado: [artefacto](https://claude.ai/artifact/MMtEeYspTmykSk6KSAv6ZC) | `biblioselect/cloud/librinova.html` (reglas de M3 copiadas en JS: `T`, `computeClock`; datos en `requests/*` y `config/clock`) | Manual en el artefacto |

Leyenda: ✅ completo · 🟡 parcial · ⚪ pendiente.

## Comandos

Sin instalar nada: abrir el repositorio en GitHub Codespaces (`.devcontainer/`); arranca el servidor solo.


Desde `biblioselect/backend`:

| Acción | Comando |
|---|---|
| Pruebas | `python -m pytest -q` |
| Pruebas de un módulo | `python -m pytest -q -k "<palabra>"` (p. ej. `cancel`, `approve`) |
| Datos demo | `python -m app.seed` |
| Servidor | `BIBLIOSELECT_DEV_AUTH=1 uvicorn app.main:app --port 8000` |

## Decisiones pendientes

| # | Módulo | Decisión | Propuesta actual |
|---|---|---|---|
| D1 | M1 | ¿ISBN/ISSN obligatorio según tipo? | Libros: ISBN o DOI; revistas: ISSN |
| D2 | M3 | Reloj en días calendario o hábiles | **Aplicado:** hábiles por defecto; `BIBLIOSELECT_CLOCK_MODE`, `BIBLIOSELECT_HOLIDAYS` |
| D3 | M3 | ¿`needs_info` pausa el reloj de biblioteca? | **Aplicado:** sí; cada estado acumula su tiempo y se reanuda al volver |
| D4 | M3 | Plazos (SLA) por etapa | **Aplicado:** recepción 2, evaluación 5, aprobación 5, presupuesto 3, adquisición 15; `BIBLIOSELECT_SLA_DAYS` |
| D5 | M4 | Aprobación secuencial o paralela; director de facultad | Secuencial; facultad solo por encima de un monto |
| D6 | M4 | Excepción de autoaprobación | Ninguna |
| D7 | M9 | Proveedor de identidad | OIDC institucional |
| D8 | M0 | Renombrar `biblioselect/` a `librinova/` | Hacerlo antes de F2 |

## Registro de cambios por módulo

Añade una línea por cambio: `AAAA-MM-DD · M# · resumen · commit`.

- 2026-10-23 · M0 M1 M3 M8 M9 M13 · MVP inicial · `e2d7df6`
- 2026-10-23 · M3 M13 · Reloj de días por etapa con semáforo en bandeja, detalle e historial
- 2026-10-23 · M13·nube M0 · Prototipo en artefacto de Claude y configuración de Codespaces
