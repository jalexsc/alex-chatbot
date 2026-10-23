# PROMPT MAESTRO — LibriNova

Plataforma de selección, evaluación, aprobación y adquisición de material bibliográfico para
bibliotecas universitarias, integrada con FOLIO.

> **Cómo usar este documento.** No lo cargues completo en cada petición. Para pedir un cambio,
> nombra el módulo (`M0`–`M13`) y consulta [`MODULOS.md`](MODULOS.md), que indica qué sección de
> este prompt y qué archivos de código leer. Este documento es la **especificación**; `MODULOS.md`
> es el **mapa**.

---

## 0. Rol y forma de trabajo

Actúa como arquitecto de software senior y desarrollador full-stack, especialista en LSP/ILS,
FOLIO (inventario, finanzas, organizaciones y órdenes), adquisiciones bibliográficas, workflows de
aprobación e integraciones REST.

Forma de trabajo obligatoria:

1. **Trabaja por módulo.** Cada cambio afecta a un módulo identificado (`M#`). Lee solo la sección
   de ese módulo, las reglas globales (§2) y los archivos que lista `MODULOS.md`.
2. **Antes de codificar** un módulo nuevo: señala ambigüedades, dependencias externas no
   confirmadas y la decisión que propones para cada una. No esperes aprobación para decisiones
   reversibles; decide, documéntalo y continúa.
3. **Entrega por incremento:** código ejecutable + pruebas + actualización de `MODULOS.md`
   (estado, archivos, decisiones).
4. **Prueba la interfaz** de lo que cambies (al menos un recorrido por HTTP o navegador), no solo
   las pruebas unitarias.
5. **No simules integraciones reales.** Si una API no está disponible, crea un adaptador de prueba
   marcado como `Fake…`/`Stub…`, y documenta qué falta para la integración real.

## 1. Alcance por fases

| Fase | Contenido | Dónde corre |
|---|---|---|
| **MVP (actual)** | Solicitudes, workflow con reloj de días, aprobaciones, auditoría, roles, interfaz web mínima | Sesión en la nube de Claude (FastAPI + SQLite) |
| F2 | FOLIO real: deduplicación, existencias, fondos, organizaciones | Servidor institucional |
| F3 | Adquisiciones: proveedores, cotizaciones, órdenes en FOLIO (mod-orders) | Servidor institucional |
| F4 | Conectores externos (OpenAlex, EBSCO KB, Mosaic, HLM, OverDrive) | Servidor institucional |
| F5 | Notificaciones (correo, WhatsApp), agente de IA, servidor MCP | Servidor institucional |
| F6 | Producción: SSO/OIDC, PostgreSQL + migraciones, Docker Compose, colas, dashboard completo | Servidor institucional |

El MVP debe poder ejecutarse sin credenciales externas.

## 2. Reglas globales (aplican a todos los módulos)

**Negocio**
- La aprobación bibliotecaria **no** equivale a autorización presupuestaria ni a orden de compra.
- Nadie aprueba su propia solicitud, salvo excepción institucional configurada explícitamente y auditada.
- Seleccionar un fondo ≠ comprometer dinero ≠ registrar contablemente. Las operaciones financieras
  reales solo se ejecutan mediante FOLIO y con los permisos correspondientes.
- No crear registros de inventario (instancia, holdings, ejemplar) al aprobar una solicitud; solo en
  el momento que definan las reglas de catalogación y recepción.
- Distinguir siempre: registro bibliográfico/instancia, holdings, ejemplar físico y licencia electrónica.
- Operaciones con compromiso financiero o irreversibles requieren confirmación humana explícita.

**Seguridad**
- Autorización validada en el servidor, nunca solo en la interfaz.
- Secretos cifrados o en gestor de secretos; nunca en texto plano, nunca al frontend, nunca en logs.
- Mínimo privilegio en usuarios y en credenciales técnicas de FOLIO y proveedores.
- Validación de entradas; protección contra inyección (incluida CQL), CSRF y exposición de errores internos.
- Ambientes separados: desarrollo, prueba, producción.

**Trazabilidad**
- Cada cambio de estado, decisión, operación externa y cambio de configuración se audita en la
  misma transacción que el cambio.
- Toda escritura externa es idempotente: id interno de operación, estado, respuesta, reintento
  seguro y reconciliación.

**IA**
- Ningún agente ni herramienta MCP puede aprobar, comprometer fondos, borrar ni ejecutar
  operaciones irreversibles, ni eludir permisos del backend.

## 3. Arquitectura

API-first, modular, con el núcleo desacoplado de los conectores:

```
Frontend ──► API (FastAPI) ──► Servicios de dominio ──► Repositorio (SQLAlchemy)
                                      │
                                      ├─► Motor de workflow + reloj de días
                                      ├─► Auditoría
                                      └─► Puertos de integración ──► Conectores (FOLIO, OpenAlex, EBSCO, …)
                                                                 └─► Notificadores (correo, WhatsApp)
```

Stack de referencia: React + TypeScript (frontend definitivo), Python + FastAPI, PostgreSQL
(SQLite en MVP), cola de trabajos para integraciones y notificaciones, Docker, OpenAPI, pytest y
pruebas E2E. Justifica cualquier tecnología adicional; no agregues dependencias innecesarias.

---

## 4. Módulos

Cada módulo define **objetivo**, **MVP** (lo mínimo que debe existir ya), **completo** (fases
posteriores), **reglas** propias y **aceptación**.

### M0 — Plataforma y configuración
- **Objetivo:** arranque, configuración por entorno, manejo de errores, despliegue.
- **MVP:** app FastAPI, `DATABASE_URL`, errores de negocio → códigos HTTP, salud (`/api/health`), datos demo.
- **Completo:** PostgreSQL + Alembic, Docker Compose, `.env.example` sin secretos, rate limiting, HTTPS, backups.
- **Aceptación:** la app arranca con un solo comando y documenta sus variables.

### M1 — Solicitudes (formulario y CRUD)
- **Objetivo:** que cualquier usuario proponga un recurso y siga su estado.
- **Campos obligatorios:** título, tipo de recurso (libro impreso, libro electrónico, revista
  impresa, revista electrónica, otro), autor(es), nombre y correo institucional del solicitante,
  facultad, programa, justificación académica.
- **Identificadores (regla condicional):** ISBN e ISSN se validan por dígito verificador cuando se
  informan. Obligatoriedad por tipo: *decisión pendiente* (propuesta: libros → ISBN o DOI;
  revistas → ISSN; otros → ninguno).
- **Complementarios:** editorial, año, edición, idioma, DOI, URL, proveedor sugerido, cantidad,
  prioridad, observaciones, adjuntos (cotización, ficha bibliográfica).
- **MVP:** crear, listar propias, ver detalle con historial, editar en estados editables, cancelar
  con motivo, identificador único legible (`BS-AAAA-XXXXXX`).
- **Completo:** adjuntos con antivirus y límite de tamaño; búsqueda de metadatos al escribir el ISBN/DOI.
- **Aceptación:** un usuario crea una solicitud y consulta su estado e historial.

### M2 — Bandeja y evaluación bibliotecaria
- **Objetivo:** que el bibliotecario evalúe pertinencia, duplicados y existencias.
- **Bandeja:** filtros por id, título, ISBN/ISSN, solicitante, facultad, programa, tipo, fecha,
  estado, responsable, prioridad; paginación; exportación autorizada.
- **Deduplicación** (usa M6): coincidencia exacta por ISBN/ISSN; probable por título normalizado
  + autor + edición + año; clasificación *exacta / probable / no encontrada*.
- **Comparación de existencias:**

  | Indicador | Fuente |
  |---|---|
  | Cantidad solicitada | Solicitud |
  | Instancias coincidentes | FOLIO inventario |
  | Holdings | FOLIO holdings |
  | Ejemplares físicos | FOLIO items |
  | Licencias electrónicas | EBSCO KB u otro sistema de licencias (M7) |
  | Cantidad propuesta | Bibliotecario (con justificación) |
  | Cantidad autorizada | Aprobadores (M4) |

- **Decisión:** enviar a aprobación, solicitar información, devolver, rechazar. Toda decisión
  registra responsable, fecha, observación y motivo.
- **MVP:** transiciones de evaluación; bandeja sin filtros avanzados.
- **Aceptación:** el bibliotecario ve coincidencias y existencias diferenciadas y registra su recomendación.

### M3 — Workflow y reloj de días
- **Objetivo:** un flujo único, configurable y medible.
- **Estados** (fuente de verdad: código del motor):

  | Etapa | Estado | Responsable |
  |---|---|---|
  | 1–2 Solicitud y recepción | `submitted` | Solicitante / sistema |
  | 3 Evaluación | `under_review`, `needs_info`, `returned_for_corrections` | Bibliotecario |
  | 4 Aprobación académica | `awaiting_approval` → `program_approved` | Director de programa (y de facultad si aplica) |
  | 5 Validación presupuestaria | `budget_approved` | Responsable presupuestario |
  | 6 Adquisición | `ordering` → `ordered` *(F3)* | Adquisiciones |
  | 7 Registro en FOLIO | `registered` *(F3)* | Adquisiciones / sistema |
  | 8 Recepción y cierre | `received` *(F3)*, `completed` | Adquisiciones / catalogación |
  | Excepciones | `rejected`, `cancelled`, `integration_error` *(F2)* | — |

- **Reloj de días (requisito visible):**
  - Cada solicitud muestra **días en la etapa actual** y **días totales** desde su creación.
  - Cada etapa tiene un plazo objetivo (SLA) configurable; el reloj se ve en **verde** (dentro del
    plazo), **ámbar** (≥ 80 % del plazo) o **rojo** (vencido).
  - El reloj aparece en la bandeja, en el detalle y en el historial (duración de cada etapa ya cerrada).
  - Se calcula a partir del historial de transiciones; no se guarda como contador manual.
  - *Decisiones pendientes:* días calendario o hábiles (y calendario de festivos); si
    `needs_info` pausa el reloj de la biblioteca.
- **Reglas:** cada transición define estado origen, destino, roles, si es aprobación y si exige motivo.
- **Completo:** aprobación paralela o secuencial configurable, delegación y sustitución, límites
  por monto, recordatorios por vencimiento (M10).
- **Aceptación:** transiciones inválidas → 409; sin rol → 403; el reloj coincide con el historial.

### M4 — Aprobaciones académicas y presupuestarias
- **Objetivo:** determinar aprobadores y registrar sus decisiones.
- **Configuración:** facultad, programa, director de programa, director de facultad, responsable
  presupuestario, biblioteca responsable, delegaciones, límites por monto, modo secuencial/paralelo.
- **Panel:** ver solicitud, evaluación, existencias, costo estimado y fondo propuesto; aprobar,
  rechazar, devolver, comentar.
- **Fondos** (usa M6): consultar fondos de FOLIO (nombre, código, estado, presupuesto, saldo si hay
  permiso, ejercicio, restricciones) y **asociar** uno a la solicitud. No autorizar si el fondo
  incumple las reglas institucionales.
- **MVP:** aprobación de programa y de presupuesto como transiciones con alcance por facultad.
- **Aceptación:** solo aprobadores autorizados deciden; nadie aprueba lo propio.

### M5 — Adquisiciones
- **Objetivo:** tramitar la compra después de las aprobaciones.
- **Proveedores:** CRUD, contactos, datos comerciales; vínculo con organizaciones de FOLIO.
- **Cotizaciones:** precio, moneda, impuestos, descuentos, envío, vigencia; comparación.
- **Compra:** confirmar material, proveedor, cantidad, precio y fondo → expediente de compra →
  orden en FOLIO (con confirmación humana) → guardar referencia de la orden.
- **Estados separados:** aprobado, comprometido, pedido enviado, recibido, disponible.
- **Integridad:** cada escritura en FOLIO pasa por un `integration_job` idempotente (§2).
- **Aceptación:** adquisiciones registra proveedor, cotización y orden sin duplicados ante reintentos.

### M6 — Conector FOLIO
- **Objetivo:** único punto de acceso a FOLIO para todos los módulos.
- **Configuración:** URL base, tenant, usuario técnico, credencial (cifrada), timeout, versión,
  estado, última conexión correcta; ambientes prueba y producción separados; botón «probar
  conexión» sin mostrar secretos.
- **Autenticación:** `POST /authn/login-with-expiry` (cookies) con renovación automática; reutilizar
  `folio_login_module.py`.
- **Endpoints a verificar en la versión instalada** (no suponer filtros arbitrarios; usar CQL):

  | Uso | Endpoint |
  |---|---|
  | Búsqueda de instancias | `GET /search/instances` (mod-search) o `GET /inventory/instances?query=` |
  | Holdings | `GET /holdings-storage/holdings?query=instanceId==…` |
  | Ejemplares | `GET /inventory/items?query=holdingsRecordId==…` |
  | Fondos y presupuestos | `GET /finance/funds`, `GET /finance/budgets` |
  | Organizaciones | `GET /organizations/organizations` |
  | Órdenes | `POST /orders/composite-orders`, `GET /orders/order-lines` |
  | Facturas | `/invoice/invoices` *(fase posterior)* |

- **MVP:** adaptador `FakeFolio` claramente marcado, con la misma interfaz que el real.
- **Aceptación:** la conexión se prueba y los errores se diagnostican sin exponer credenciales.

### M7 — Conectores externos y comparación unificada
- **Servicios:** OpenAlex (metadatos y contexto académico, nunca criterio automático de compra),
  EBSCO Knowledge Base (cobertura, suscripciones existentes), Mosaic, HLM, OverDrive y otros.
- **Por conector:** nombre, endpoint, método de autenticación, credenciales (cifradas), parámetros,
  capacidades, límites de uso, estado, última sincronización, errores recientes.
- **Sin API:** importación de archivo normalizado o registro manual.
- **Vista unificada:** fuente, título, autor, ISBN/ISSN/DOI, editorial, año, tipo, disponibilidad,
  cobertura, enlace, fecha de consulta y confianza; distinguir dato confirmado, no disponible e inferido.
- **Aceptación:** se puede activar un conector nuevo sin modificar el núcleo.

### M8 — Auditoría y monitoreo
- **Eventos:** sesiones, creación y edición de solicitudes, cambios de estado, decisiones, cambios
  de responsables, cantidades, fondos y proveedores, operaciones en FOLIO, errores de integración,
  notificaciones, reintentos, cambios de configuración.
- **Campos:** fecha y hora, actor (usuario o servicio), operación, entidad, id de solicitud,
  resultado, descripción, id de correlación.
- **Reglas:** solo admin y auditor leen; registro de solo inserción; retención configurable; sin secretos.

### M9 — Usuarios, roles y autenticación
- **Roles:** solicitante, bibliotecario evaluador, director de programa, director de facultad,
  responsable presupuestario, adquisiciones, catalogador, administrador, auditor. Un usuario puede
  tener varios.
- **Alcance:** por facultad y programa.
- **MVP:** identidad de desarrollo (`X-Dev-User`, solo con `BIBLIOSELECT_DEV_AUTH=1`), CRUD de usuarios por admin.
- **Completo:** SSO/OIDC institucional, sesiones, recuperación de acceso, historial de cambios de permisos.

### M10 — Notificaciones
- **Correo** (SMTP o API) y **WhatsApp Business** (plantillas aprobadas, consentimiento).
- **Eventos:** recibida, incompleta, evaluada, pendiente de aprobación, aprobada/rechazada,
  devuelta, compra autorizada, pedido enviado, material recibido, finalizada, **plazo por vencer o vencido** (M3).
- **Contenido:** id, estado y enlace autenticado. Cada envío se registra en `notification_jobs` y en auditoría.

### M11 — Agente de IA y servidor MCP
- **Agente:** resumir solicitudes, comparar ediciones, señalar duplicados e inconsistencias para
  revisión humana, sugerir recursos, redactar notificaciones, informar pendientes.
- **MCP:** herramientas de lectura (`search_requests`, `get_request_details`,
  `check_folio_inventory`, `compare_resources`, `get_fund_information`, `get_pending_approvals`,
  `draft_notification`) separadas de las de escritura (`send_notification`,
  `prepare_acquisition`); autenticación, autorización por herramienta, validación y auditoría.
- **Regla:** pasa siempre por los servicios del backend; nunca accede directo a la base ni a FOLIO.

### M12 — Dashboard e informes
- **Indicadores:** totales; pendientes de evaluación y aprobación; aprobadas y rechazadas;
  **tiempo medio por etapa y solicitudes vencidas** (M3); por facultad, programa y tipo;
  duplicados detectados; cantidad solicitada frente a recomendada; adquisiciones por proveedor;
  gasto por fondo y período; errores de integración.
- **Filtros:** período, facultad, programa, estado, proveedor, tipo. Exportación CSV/Excel según permisos.

### M13 — Interfaz y diseño
- Profesional y sobrio, adaptable a móvil, accesible (contraste, teclado, etiquetas).
- Menú lateral por módulo, dashboard inicial, tablas con filtros, formularios con validación clara,
  indicadores de estado y reloj, detalle con historial cronológico, panel de aprobaciones, panel
  de integraciones.
- Nunca mostrar credenciales ni datos sensibles.

---

## 5. Modelo de datos (por módulo)

| Módulo | Tablas |
|---|---|
| M1 | `bibliographic_requests`, `request_identifiers`, `request_attachments` |
| M2 | `request_evaluations`, `inventory_matches`, `holdings_comparisons` |
| M3 | `workflow_history`, `stage_sla_settings` |
| M4 | `faculties`, `academic_programs`, `approval_rules`, `approvals`, `funds` (caché con fecha), `budget_validations` |
| M5 | `vendors`, `quotations`, `acquisitions`, `purchase_order_references` |
| M6, M7 | `integration_connections`, `integration_jobs` |
| M8 | `audit_logs` |
| M9 | `users`, `roles`, `permissions`, `user_roles` |
| M10 | `notification_templates`, `notification_jobs` |
| M11 | `agent_actions` |

No dupliques datos cuyo sistema de registro es FOLIO: guarda referencias externas y resultados de
consulta con fecha y política de actualización.

## 6. Criterios de aceptación globales

1. Un usuario crea una solicitud y consulta su estado, historial y reloj de días.
2. Un bibliotecario evalúa y compara con FOLIO, diferenciando instancias, holdings, ejemplares y licencias.
3. Los aprobadores autorizados aprueban o rechazan; nadie aprueba lo propio.
4. El fondo se consulta y asocia según permisos.
5. Adquisiciones registra proveedores, cotizaciones y órdenes sin duplicados.
6. Las integraciones se prueban y sus errores se diagnostican.
7. Toda decisión y operación sensible queda auditada.
8. Las notificaciones configuradas llegan y quedan registradas.
9. Ningún agente de IA elude autorizaciones.
10. Hay pruebas, documentación e instrucciones de despliegue.
