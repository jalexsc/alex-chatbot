"""Máquina de estados del flujo de solicitudes y reglas de quién puede ejecutar cada transición.

Reglas clave:
- La aprobación bibliotecaria (enviar a aprobación) NO autoriza presupuesto ni compra.
- Ninguna transición de aprobación puede ejecutarla el propio solicitante.
- El solicitante actúa solo sobre sus propias solicitudes (rol ``REQUESTER`` = dueño).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    REQUESTER = "requester"  # dueño de la solicitud, no es un rol global
    LIBRARIAN = "librarian"
    PROGRAM_DIRECTOR = "program_director"
    BUDGET_OFFICER = "budget_officer"
    ACQUISITIONS = "acquisitions"
    ADMIN = "admin"
    AUDITOR = "auditor"


class Status(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_INFO = "needs_info"
    RETURNED = "returned_for_corrections"
    AWAITING_APPROVAL = "awaiting_approval"
    PROGRAM_APPROVED = "program_approved"
    BUDGET_APPROVED = "budget_approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


#: Estados en los que el solicitante puede modificar o cancelar su solicitud.
EDITABLE_STATUSES = frozenset({Status.SUBMITTED, Status.NEEDS_INFO, Status.RETURNED})
TERMINAL_STATUSES = frozenset({Status.REJECTED, Status.CANCELLED, Status.COMPLETED})
#: Roles que pueden cancelar en cualquier estado no terminal.
CANCEL_ROLES = frozenset({Role.LIBRARIAN, Role.ADMIN})


@dataclass(frozen=True)
class Transition:
    action: str
    source: Status
    target: Status
    roles: frozenset[Role]
    approval: bool = False  # decisión de aprobación: el solicitante no puede ejecutarla
    requires_reason: bool = False


_T = Transition
_LIB = frozenset({Role.LIBRARIAN})

TRANSITIONS: dict[str, Transition] = {
    t.action: t
    for t in (
        _T("start_review", Status.SUBMITTED, Status.UNDER_REVIEW, _LIB),
        _T("request_info", Status.UNDER_REVIEW, Status.NEEDS_INFO, _LIB, requires_reason=True),
        _T("return_for_corrections", Status.UNDER_REVIEW, Status.RETURNED, _LIB, requires_reason=True),
        _T("send_to_approval", Status.UNDER_REVIEW, Status.AWAITING_APPROVAL, _LIB),
        _T("reject_library", Status.UNDER_REVIEW, Status.REJECTED, _LIB, requires_reason=True),
        _T("answer_info", Status.NEEDS_INFO, Status.UNDER_REVIEW, frozenset({Role.REQUESTER})),
        _T("resubmit", Status.RETURNED, Status.SUBMITTED, frozenset({Role.REQUESTER})),
        _T("approve_program", Status.AWAITING_APPROVAL, Status.PROGRAM_APPROVED,
           frozenset({Role.PROGRAM_DIRECTOR}), approval=True),
        _T("reject_program", Status.AWAITING_APPROVAL, Status.REJECTED,
           frozenset({Role.PROGRAM_DIRECTOR}), approval=True, requires_reason=True),
        _T("return_program", Status.AWAITING_APPROVAL, Status.RETURNED,
           frozenset({Role.PROGRAM_DIRECTOR}), requires_reason=True),
        _T("approve_budget", Status.PROGRAM_APPROVED, Status.BUDGET_APPROVED,
           frozenset({Role.BUDGET_OFFICER}), approval=True),
        _T("reject_budget", Status.PROGRAM_APPROVED, Status.REJECTED,
           frozenset({Role.BUDGET_OFFICER}), approval=True, requires_reason=True),
        _T("complete_acquisition", Status.BUDGET_APPROVED, Status.COMPLETED,
           frozenset({Role.ACQUISITIONS})),
    )
}
