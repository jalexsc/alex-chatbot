"""Contratos de entrada de la API, con validación de formato."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .identifiers import is_valid_isbn, is_valid_issn, normalize_identifier
from .workflow import Role

MaterialType = Literal["print_book", "ebook", "print_journal", "ebook_journal", "other"]
Priority = Literal["low", "normal", "high"]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
URL_PATTERN = r"^https?://\S+$"


class RequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=500)
    material_type: MaterialType
    isbn: str | None = Field(default=None, max_length=30)
    issn: str | None = Field(default=None, max_length=12)
    authors: str = Field(min_length=2, max_length=1000)
    requester_name: str = Field(min_length=2, max_length=200)
    requester_email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    faculty: str = Field(min_length=2, max_length=200)
    program: str = Field(min_length=2, max_length=200)
    justification: str = Field(min_length=20, max_length=5000)
    publisher: str | None = Field(default=None, max_length=200)
    publication_year: int | None = Field(default=None, ge=1450)
    edition: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=50)
    doi: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500, pattern=URL_PATTERN)
    suggested_vendor: str | None = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=1, le=500)
    priority: Priority = "normal"
    observations: str | None = Field(default=None, max_length=2000)

    @field_validator("isbn")
    @classmethod
    def _isbn(cls, v: str | None) -> str | None:
        if not v or not v.strip():
            return None
        if not is_valid_isbn(v):
            raise ValueError("ISBN no válido (revise el dígito verificador).")
        return normalize_identifier(v)

    @field_validator("issn")
    @classmethod
    def _issn(cls, v: str | None) -> str | None:
        if not v or not v.strip():
            return None
        if not is_valid_issn(v):
            raise ValueError("ISSN no válido (revise el dígito verificador).")
        return normalize_identifier(v)

    @field_validator("publication_year")
    @classmethod
    def _year(cls, v: int | None) -> int | None:
        if v is not None and v > date.today().year + 1:
            raise ValueError("Año de publicación fuera de rango.")
        return v


class TransitionIn(BaseModel):
    action: str = Field(min_length=1, max_length=60)
    reason: str | None = Field(default=None, max_length=1000)


class CancelIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class UserIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    full_name: str = Field(min_length=2, max_length=200)
    faculty: str | None = Field(default=None, max_length=200)
    roles: list[Role] = Field(default_factory=list)
    active: bool = True


def request_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Filtra un dict a los campos que acepta RequestIn (usado al actualizar)."""
    return {k: v for k, v in data.items() if k in RequestIn.model_fields}
