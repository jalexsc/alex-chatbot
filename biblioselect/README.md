# BiblioSelect · MVP de solicitudes bibliográficas

Plataforma para recibir, evaluar, aprobar y tramitar solicitudes de material bibliográfico.
Este MVP cubre el **núcleo del flujo**: solicitud → evaluación bibliotecaria → aprobación del
programa → validación presupuestaria → cierre de adquisición, con historial, auditoría y permisos
en el servidor.

## Qué incluye (MVP)

| Área | Estado |
|---|---|
| Formulario de solicitud con validación de ISBN-10/13 e ISSN (dígito verificador) | Hecho |
| CRUD: crear, consultar, modificar (solo en estados editables), cancelar | Hecho |
| Máquina de estados con transiciones por rol | Hecho |
| Regla: nadie aprueba su propia solicitud; aprobación bibliotecaria ≠ presupuesto | Hecho |
| Alcance por facultad para directores de programa | Hecho |
| Historial cronológico por solicitud | Hecho |
| Bitácora de auditoría (consulta solo para admin/auditor) | Hecho |
| Administración de usuarios y roles (admin) | Hecho |
| Interfaz web mínima (una página estática) | Hecho |
| Reloj de días por etapa con semáforo (verde, ámbar, rojo) | Hecho |
| Autenticación institucional (SSO/OIDC) | **Pendiente** — MVP usa identidad de desarrollo |
| Conector FOLIO (búsqueda de duplicados, existencias, fondos, pedidos) | **Pendiente** |
| Notificaciones por correo y WhatsApp | **Pendiente** |
| Agente de IA y servidor MCP | **Pendiente** |
| Adjuntos (cotizaciones, fichas) | **Pendiente** |
| Dashboard, exportaciones CSV/Excel | **Pendiente** |
| Gestión de proveedores y cotizaciones | **Pendiente** |
| Migraciones (Alembic) y Docker Compose con PostgreSQL | **Pendiente** |

## Ejecutar en local

Desde `biblioselect/backend`:

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                                   # usuarios demo, uno por rol
BIBLIOSELECT_DEV_AUTH=1 uvicorn app.main:app --reload --port 8000
```

Abrir http://localhost:8000 e introducir uno de los correos demo:

| Correo | Rol |
|---|---|
| `docente@example.edu` | Solicitante (facultad de Ingeniería) |
| `bibliotecario@example.edu` | Bibliotecario evaluador |
| `director.programa@example.edu` | Director de programa (facultad de Ingeniería) |
| `presupuesto@example.edu` | Responsable presupuestario |
| `adquisiciones@example.edu` | Adquisiciones |
| `admin@example.edu` | Administrador |
| `auditor@example.edu` | Auditor |

Pruebas:

```bash
python -m pytest -q
```

Documentación interactiva de la API: http://localhost:8000/docs

## Variables de entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./biblioselect.db` | Conexión a la base de datos |
| `BIBLIOSELECT_DEV_AUTH` | (apagado) | `1` activa la identidad de desarrollo |
| `BIBLIOSELECT_CLOCK_MODE` | `business` | Reloj en días `business` (hábiles) o `calendar` |
| `BIBLIOSELECT_HOLIDAYS` | (vacío) | Festivos, separados por coma: `2026-12-08,2026-12-25` |
| `BIBLIOSELECT_SLA_DAYS` | ver `app/clock.py` | Plazos por estado en JSON: `{"under_review": 7}` |
| `BIBLIOSELECT_TZ` | UTC | Zona horaria para cortar los días: `America/Bogota` |

## Autenticación de desarrollo

Sin `BIBLIOSELECT_DEV_AUTH=1` la API responde 401 a todas las rutas protegidas. Con esa variable,
cada petición debe incluir la cabecera `X-Dev-User: <correo>`. **Esto no es seguro para uso
institucional:** cualquiera puede suplantar un correo. Antes de producción debe reemplazarse
`current_user` en `app/main.py` por validación de token OIDC/SSO.

## Reglas de negocio implementadas

- **Estados:** `submitted`, `under_review`, `needs_info`, `returned_for_corrections`,
  `awaiting_approval`, `program_approved`, `budget_approved`, `rejected`, `cancelled`, `completed`.
  Definidos en `app/workflow.py`.
- **Edición:** solo el solicitante, y solo en `submitted`, `needs_info` o `returned_for_corrections`.
- **Cancelación:** el solicitante en estados editables; bibliotecario o admin en cualquier estado no terminal.
- **Aprobaciones** (`approve_*`): no pueden ejecutarlas el solicitante ni nadie que no tenga el rol.
- **Motivo obligatorio** en rechazos, devoluciones, solicitudes de información y cancelaciones.
- **Lectura:** el personal de biblioteca, presupuesto, adquisiciones, admin y auditor ven todo;
  el director de programa solo su facultad; el solicitante solo lo suyo. Un recurso no visible responde
  404, sin revelar si existe.
- **Auditoría:** cada creación, edición, transición y cancelación escribe en `audit_logs` dentro de la
  misma transacción que el cambio.

## Decisiones pendientes (para validar con la biblioteca)

1. **Quién puede solicitar:** hoy cualquier usuario autenticado puede crear solicitudes. ¿Debe limitarse
   a correos institucionales o a un rol?
2. **Obligatoriedad de ISBN/ISSN:** hoy son opcionales y se validan si se indican. ¿Libros impresos
   deben llevar ISBN?
3. **Cadena de aprobación:** el flujo es secuencial (biblioteca → programa → presupuesto). Falta modelar
   aprobación de director de facultad, paralelismo y límites por monto.
4. **Excepción de autoaprobación:** hoy no existe excepción. Confirmar si alguna figura lo requiere.
5. **Integración FOLIO:** definir si la búsqueda de duplicados y la creación de pedidos se harán
   desde este MVP o en una fase posterior, y validar endpoints contra la versión de FOLIO instalada.

## Estructura

```
biblioselect/
├── README.md
└── backend/
    ├── requirements.txt
    ├── app/
    │   ├── main.py         # API FastAPI y configuración
    │   ├── service.py      # casos de uso: permisos, transiciones, auditoría
    │   ├── workflow.py     # estados, transiciones y roles
    │   ├── schemas.py      # validación de entrada
    │   ├── identifiers.py  # ISBN / ISSN
    │   ├── db.py           # modelo SQLAlchemy
    │   ├── errors.py       # errores de negocio → códigos HTTP
    │   ├── seed.py         # usuarios demo
    │   └── static/index.html
    └── tests/
```
