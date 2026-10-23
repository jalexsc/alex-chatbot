"""Errores de negocio. Cada uno lleva el código HTTP con el que la API responde."""
from __future__ import annotations


class DomainError(Exception):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


class ForbiddenError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409


class BusinessRuleError(DomainError):
    status_code = 422
