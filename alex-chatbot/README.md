# Alex · Chatbot de biblioteca

React + FastAPI + Claude (tool use). Alex consulta FOLIO reutilizando `folio_login_module.py` de la raíz del proyecto.

```
frontend (React/Vite :5173) --/api/chat--> backend (FastAPI :8000) --> Claude
                                                  └── SourceRegistry ── FolioSource ── folio_login_module ── FOLIO
```

## Arranque

Backend (desde `alex-chatbot/backend`):
```
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env    # completar ANTHROPIC_API_KEY
..\..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Frontend (requiere Node 18+), desde `alex-chatbot/frontend`:
```
npm install
npm run dev
```
Abrir http://localhost:5173.

## Agregar otra fuente de datos

1. Crear `backend/sources/<fuente>.py` con una clase que herede de `DataSource`
   (`name`, `tools()`, `call()`); nombrar las tools con el prefijo `<name>_`.
2. Registrarla en la lista de `SourceRegistry` en `backend/main.py`.

Claude decide qué tools usar; no hay que tocar el agente ni el frontend.

## Seguridad

- La clave de Anthropic y las credenciales de FOLIO viven solo en el backend.
- Las tools son de solo lectura y no exponen datos de usuarios (patrons).
- Los valores del usuario se escapan antes de armar consultas CQL.
