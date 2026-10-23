"""API de BiblioSelect. Ejecutar desde biblioselect/backend:  uvicorn app.main:app --reload

Autenticación: MVP con identidad de desarrollo (cabecera ``X-Dev-User: <correo>``), activa solo
con ``BIBLIOSELECT_DEV_AUTH=1``. Debe sustituirse por SSO/OIDC institucional antes de producción.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from . import service
from .db import AuditLog, Base, BibliographicRequest, User, UserRole, WorkflowEntry
from .errors import DomainError
from .schemas import CancelIn, RequestIn, TransitionIn, UserIn
from .workflow import Role

STATIC_DIR = Path(__file__).parent / "static"


def _serialize_request(req: BibliographicRequest, actions: list[str] | None = None) -> dict[str, Any]:
    data = {
        "id": req.id,
        "reference": req.reference,
        "status": req.status,
        "title": req.title,
        "material_type": req.material_type,
        "isbn": req.isbn,
        "issn": req.issn,
        "authors": req.authors,
        "requester_name": req.requester_name,
        "requester_email": req.requester_email,
        "faculty": req.faculty,
        "program": req.program,
        "justification": req.justification,
        "publisher": req.publisher,
        "publication_year": req.publication_year,
        "edition": req.edition,
        "language": req.language,
        "doi": req.doi,
        "url": req.url,
        "suggested_vendor": req.suggested_vendor,
        "quantity": req.quantity,
        "priority": req.priority,
        "observations": req.observations,
        "cancel_reason": req.cancel_reason,
        "created_at": req.created_at.isoformat(),
        "updated_at": req.updated_at.isoformat(),
    }
    if actions is not None:
        data["available_actions"] = actions
    return data


def _serialize_history(entries: list[WorkflowEntry]) -> list[dict[str, Any]]:
    return [
        {
            "from_status": e.from_status,
            "to_status": e.to_status,
            "action": e.action,
            "actor_email": e.actor_email,
            "reason": e.reason,
            "at": e.created_at.isoformat(),
        }
        for e in entries
    ]


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "email": user.email,
        "full_name": user.full_name,
        "faculty": user.faculty,
        "roles": sorted(user.role_set()),
        "active": user.active,
    }


def create_app(database_url: str | None = None, dev_auth: bool | None = None) -> FastAPI:
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///./biblioselect.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    dev_enabled = dev_auth if dev_auth is not None else os.getenv("BIBLIOSELECT_DEV_AUTH") == "1"

    app = FastAPI(title="BiblioSelect", version="0.1.0")

    def get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def current_user(
        db: Session = Depends(get_db),
        x_dev_user: str | None = Header(default=None),
    ) -> User:
        if not dev_enabled or not x_dev_user:
            raise HTTPException(status_code=401, detail="No autenticado.")
        user = db.scalar(select(User).where(User.email == x_dev_user.strip().lower(), User.active.is_(True)))
        if user is None:
            raise HTTPException(status_code=401, detail="No autenticado.")
        return user

    def require_roles(*roles: Role):
        def checker(user: User = Depends(current_user)) -> User:
            if not user.role_set() & set(roles):
                raise HTTPException(status_code=403, detail="Permisos insuficientes.")
            return user

        return checker

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "dev_auth": dev_enabled}

    @app.get("/api/me")
    def me(user: User = Depends(current_user)) -> dict[str, Any]:
        return _serialize_user(user)

    @app.post("/api/requests", status_code=201)
    def create_request(payload: RequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        req = service.create_request(db, user, payload)
        return _serialize_request(req, service.available_actions(user, req))

    @app.get("/api/requests")
    def list_requests(
        status: str | None = Query(default=None, max_length=40),
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        items = service.list_requests(db, user, status)
        return [_serialize_request(r) for r in items]

    @app.get("/api/requests/{request_id}")
    def get_request(request_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        req = service.get_request(db, user, request_id)
        return _serialize_request(req, service.available_actions(user, req))

    @app.patch("/api/requests/{request_id}")
    def update_request(
        request_id: str,
        changes: dict[str, Any],
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        req = service.update_request(db, user, request_id, changes)
        return _serialize_request(req, service.available_actions(user, req))

    @app.post("/api/requests/{request_id}/transitions")
    def transition(
        request_id: str,
        payload: TransitionIn,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        req = service.apply_transition(db, user, request_id, payload)
        return _serialize_request(req, service.available_actions(user, req))

    @app.post("/api/requests/{request_id}/cancel")
    def cancel(request_id: str, payload: CancelIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        req = service.cancel_request(db, user, request_id, payload.reason)
        return _serialize_request(req, service.available_actions(user, req))

    @app.get("/api/requests/{request_id}/history")
    def request_history(request_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return _serialize_history(service.history(db, user, request_id))

    @app.post("/api/admin/users", status_code=201)
    def create_user(
        payload: UserIn,
        _: User = Depends(require_roles(Role.ADMIN)),
        db: Session = Depends(get_db),
    ):
        email = payload.email.strip().lower()
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise HTTPException(status_code=409, detail="El correo ya está registrado.")
        user = User(email=email, full_name=payload.full_name, faculty=payload.faculty, active=payload.active)
        user.roles = [UserRole(role=r.value) for r in payload.roles]
        db.add(user)
        db.commit()
        return _serialize_user(user)

    @app.get("/api/audit")
    def audit_log(
        request_id: str | None = Query(default=None, max_length=36),
        limit: int = Query(default=100, ge=1, le=500),
        _: User = Depends(require_roles(Role.ADMIN, Role.AUDITOR)),
        db: Session = Depends(get_db),
    ):
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        if request_id:
            stmt = stmt.where(AuditLog.request_id == request_id)
        return [
            {
                "at": row.occurred_at.isoformat(),
                "actor_email": row.actor_email,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "request_id": row.request_id,
                "result": row.result,
                "description": row.description,
                "correlation_id": row.correlation_id,
            }
            for row in db.scalars(stmt).all()
        ]

    app.state.session_factory = session_factory
    return app


app = create_app()
