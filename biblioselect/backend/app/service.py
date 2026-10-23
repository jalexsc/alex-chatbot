"""Casos de uso: crear, editar, transicionar y cancelar solicitudes, con auditoría en la misma transacción."""
from __future__ import annotations

import secrets
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .db import AuditLog, BibliographicRequest, User, WorkflowEntry, utcnow
from .errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from .schemas import RequestIn, TransitionIn, request_fields
from .workflow import (
    CANCEL_ROLES,
    EDITABLE_STATUSES,
    TERMINAL_STATUSES,
    TRANSITIONS,
    Role,
    Status,
    Transition,
)

#: Roles que ven todas las solicitudes (además de su dueño).
STAFF_ROLES = frozenset({Role.ADMIN, Role.LIBRARIAN, Role.AUDITOR, Role.BUDGET_OFFICER, Role.ACQUISITIONS})

#: Campos que el solicitante no puede cambiar al actualizar.
_PROTECTED_FIELDS = {"requester_email"}


# ---------- auditoría ----------

def audit(
    db: Session,
    actor: User | None,
    action: str,
    *,
    entity: str,
    entity_id: str | None,
    request_id: str | None,
    description: str,
    result: str = "ok",
    correlation_id: str | None = None,
) -> None:
    db.add(
        AuditLog(
            occurred_at=utcnow(),
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            request_id=request_id,
            result=result,
            description=description,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
    )


# ---------- permisos de lectura ----------

def can_view(actor: User, req: BibliographicRequest) -> bool:
    roles = actor.role_set()
    if roles & STAFF_ROLES:
        return True
    if req.requester_id == actor.id:
        return True
    return Role.PROGRAM_DIRECTOR in roles and actor.faculty is not None and actor.faculty == req.faculty


def _get_visible(db: Session, actor: User, request_id: str) -> BibliographicRequest:
    req = db.get(BibliographicRequest, request_id)
    if req is None or not can_view(actor, req):
        # Respuesta idéntica para "no existe" y "no autorizado": no revela existencia.
        raise NotFoundError("Solicitud no encontrada.")
    return req


def list_requests(db: Session, actor: User, status: str | None = None) -> list[BibliographicRequest]:
    stmt = select(BibliographicRequest).order_by(BibliographicRequest.created_at.desc())
    if not actor.role_set() & STAFF_ROLES:
        conditions = [BibliographicRequest.requester_id == actor.id]
        if Role.PROGRAM_DIRECTOR in actor.role_set() and actor.faculty:
            conditions.append(BibliographicRequest.faculty == actor.faculty)
        stmt = stmt.where(or_(*conditions))
    if status:
        stmt = stmt.where(BibliographicRequest.status == status)
    return list(db.scalars(stmt).all())


def get_request(db: Session, actor: User, request_id: str) -> BibliographicRequest:
    return _get_visible(db, actor, request_id)


def history(db: Session, actor: User, request_id: str) -> list[WorkflowEntry]:
    req = _get_visible(db, actor, request_id)
    return list(
        db.scalars(
            select(WorkflowEntry).where(WorkflowEntry.request_id == req.id).order_by(WorkflowEntry.id)
        ).all()
    )


# ---------- reglas de transición ----------

def _is_owner(actor: User, req: BibliographicRequest) -> bool:
    return req.requester_id == actor.id


def _can_execute(actor: User, req: BibliographicRequest, t: Transition) -> bool:
    if t.approval and _is_owner(actor, req):
        return False  # nadie aprueba su propia solicitud (sin excepciones en el MVP)
    roles = actor.role_set()
    if Role.REQUESTER in t.roles and _is_owner(actor, req):
        return True
    if Role.PROGRAM_DIRECTOR in t.roles and Role.PROGRAM_DIRECTOR in roles:
        return actor.faculty == req.faculty  # director solo de su facultad
    return bool(roles & {r for r in t.roles if r != Role.REQUESTER})


def available_actions(actor: User, req: BibliographicRequest) -> list[str]:
    if not can_view(actor, req) or req.status in TERMINAL_STATUSES:
        return []
    actions = [
        t.action
        for t in TRANSITIONS.values()
        if t.source == req.status and _can_execute(actor, req, t)
    ]
    if _can_cancel(actor, req):
        actions.append("cancel")
    return actions


def _can_cancel(actor: User, req: BibliographicRequest) -> bool:
    if req.status in TERMINAL_STATUSES:
        return False
    if _is_owner(actor, req) and req.status in EDITABLE_STATUSES:
        return True
    return bool(actor.role_set() & CANCEL_ROLES)


def _record(
    db: Session,
    req: BibliographicRequest,
    actor: User,
    action: str,
    from_status: str | None,
    to_status: str,
    reason: str | None,
) -> None:
    db.add(
        WorkflowEntry(
            request_id=req.id,
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_id=actor.id,
            actor_email=actor.email,
            reason=reason,
            created_at=utcnow(),
        )
    )


# ---------- casos de uso ----------

def create_request(db: Session, actor: User, payload: RequestIn) -> BibliographicRequest:
    req = BibliographicRequest(
        id=str(uuid.uuid4()),
        reference=f"BS-{utcnow().year}-{secrets.token_hex(3).upper()}",
        requester_id=actor.id,
        status=Status.SUBMITTED,
        **payload.model_dump(),
    )
    db.add(req)
    db.flush()
    _record(db, req, actor, "create", None, Status.SUBMITTED, None)
    audit(db, actor, "request.create", entity="request", entity_id=req.id, request_id=req.id,
          description=f"Solicitud {req.reference} creada")
    db.commit()
    return req


def update_request(db: Session, actor: User, request_id: str, changes: dict[str, Any]) -> BibliographicRequest:
    req = _get_visible(db, actor, request_id)
    if not _is_owner(actor, req):
        raise ForbiddenError("Solo el solicitante puede modificar la solicitud.")
    if req.status not in EDITABLE_STATUSES:
        raise ConflictError(f"La solicitud no se puede modificar en estado '{req.status}'.")
    changes = {k: v for k, v in request_fields(changes).items() if k not in _PROTECTED_FIELDS}
    if not changes:
        raise BusinessRuleError("No hay campos modificables en la solicitud.")

    current = {k: getattr(req, k) for k in RequestIn.model_fields}
    try:
        validated = RequestIn(**{**current, **changes}).model_dump()  # valida el resultado completo
    except ValidationError as exc:
        raise BusinessRuleError(exc.errors()[0]["msg"].removeprefix("Value error, ")) from exc
    for field in changes:
        setattr(req, field, validated[field])
    db.flush()
    audit(db, actor, "request.update", entity="request", entity_id=req.id, request_id=req.id,
          description=f"Campos modificados: {', '.join(sorted(changes))}")
    db.commit()
    return req


def apply_transition(db: Session, actor: User, request_id: str, payload: TransitionIn) -> BibliographicRequest:
    req = _get_visible(db, actor, request_id)
    if payload.action == "cancel":
        raise BusinessRuleError("Use el endpoint de cancelación.")
    t = TRANSITIONS.get(payload.action)
    if t is None:
        raise BusinessRuleError(f"Acción desconocida: {payload.action}")
    if req.status != t.source:
        raise ConflictError(f"La acción '{t.action}' requiere estado '{t.source}' (actual: '{req.status}').")
    if not _can_execute(actor, req, t):
        raise ForbiddenError("No tiene permiso para esta acción sobre la solicitud.")
    reason = (payload.reason or "").strip() or None
    if t.requires_reason and not reason:
        raise BusinessRuleError("Esta acción requiere un motivo.")

    previous = req.status
    req.status = t.target
    _record(db, req, actor, t.action, previous, t.target, reason)
    audit(db, actor, f"request.{t.action}", entity="request", entity_id=req.id, request_id=req.id,
          description=f"{previous} -> {t.target}")
    db.commit()
    return req


def cancel_request(db: Session, actor: User, request_id: str, reason: str) -> BibliographicRequest:
    req = _get_visible(db, actor, request_id)
    if not _can_cancel(actor, req):
        if req.status in TERMINAL_STATUSES:
            raise ConflictError(f"La solicitud ya está en estado terminal '{req.status}'.")
        raise ForbiddenError("No tiene permiso para cancelar esta solicitud en su estado actual.")
    previous = req.status
    req.status = Status.CANCELLED
    req.cancel_reason = reason.strip()
    _record(db, req, actor, "cancel", previous, Status.CANCELLED, req.cancel_reason)
    audit(db, actor, "request.cancel", entity="request", entity_id=req.id, request_id=req.id,
          description=f"{previous} -> cancelled")
    db.commit()
    return req
