# Alex - Asistente de biblioteca

## Objetivo
Chatbot conversacional (Alex) que ayuda a usuarios y personal bibliotecario a buscar
materiales, revisar ejemplares y disponibilidad en el catálogo de la biblioteca, consultando
FOLIO en tiempo real. Solo lectura: no hace préstamos, renovaciones ni expone datos de
usuarios (patrons).

## Stack
- Frontend: React + Vite (carpeta `alex-chatbot/frontend`)
- Backend: FastAPI + Python 3.11 (carpeta `alex-chatbot/backend`)
- IA: API de Claude (Anthropic), tool use para decidir qué consultar en FOLIO
- Datos: FOLIO (Okapi), vía `folio_login_module.py` (raíz del repo, sesión por cookies)

## Estructura
- `alex-chatbot/backend/main.py` → API FastAPI (`/api/chat`, `/api/health`), registro de fuentes
- `alex-chatbot/backend/agent.py` → bucle de conversación con Claude + tool use
- `alex-chatbot/backend/sources/` → fuentes de datos (`base.py` = interfaz `DataSource`,
  `folio.py` = herramientas de solo lectura sobre FOLIO). Nuevas fuentes (Alma, Koha, etc.)
  se agregan aquí y se registran en `main.py`
- `alex-chatbot/frontend/src/` → `App.jsx`, `components/` (chat, avatar de Alex), `api.js`
  (cliente del backend)
- `folio_login_module.py` (raíz del repo) → cliente reutilizado de autenticación FOLIO

## Comandos
- Backend: `uvicorn main:app --reload --port 8000` (desde `alex-chatbot/backend`, con el
  venv activado)
- Frontend: `npm run dev` (desde `alex-chatbot/frontend`)
- Tests: aún no hay suite configurada (pendiente `pytest` / `vitest`)
- Lint: aún no hay lint configurado (pendiente `ruff check .` / `eslint`)

## Convenciones de código
- Python: type hints, funciones cortas, docstrings solo si aportan
- React: componentes funcionales, hooks, sin lógica de negocio en la UI
- Nombres en inglés en el código; comentarios y commits en español
- No duplicar código: reutilizar lo existente antes de crear algo nuevo (p. ej. `DataSource`
  como interfaz común para nuevas fuentes)

## Reglas de calidad
- Manejar errores explícitamente (sin `except:` vacíos)
- Validar entradas con Pydantic (ver `ChatRequest`/`Message` en `main.py`)
- Añadir o actualizar tests con cada cambio, una vez exista la suite
- Cambios pequeños y enfocados; no refactorizar código no relacionado

## Seguridad
- Nunca commitear `.env` ni `okapi_customers.json` (credenciales reales de FOLIO) — ambos
  están en `.gitignore` a propósito
- Mantener `alex-chatbot/backend/.env.example` actualizado como plantilla, sin valores reales
- Usar variables de entorno (`ANTHROPIC_API_KEY`, `FOLIO_LIBRARY`, `FOLIO_CUSTOMERS_JSON`,
  `ALEX_CORS_ORIGINS`)
- No registrar datos sensibles en logs (contraseñas de FOLIO nunca se loguean; ver
  `folio_login_module.py`)
- Las herramientas de FOLIO son de solo lectura y no exponen datos de usuarios/patrons; no
  agregar tools que sí lo hagan sin revisión explícita

## Definición de "terminado"
- [ ] Funciona y se probó localmente (backend + frontend, o al menos vía `curl`/`Invoke-RestMethod`)
- [ ] Tests pasan y lint sin errores (una vez exista la suite)
- [ ] Sin código muerto ni `console.log`/`print` de depuración

## Fuera de alcance / no hacer
- No cambiar dependencias (`requirements.txt`, `package.json`) sin avisar
- No tocar `okapi_customers.json` ni `.env` salvo para configurarlos localmente; nunca subirlos
  al repo
- No agregar herramientas que expongan datos de usuarios/patrons sin aprobación explícita
