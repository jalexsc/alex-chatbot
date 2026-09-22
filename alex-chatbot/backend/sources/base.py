"""Contrato común para todas las fuentes de datos de Alex (FOLIO, y las que vengan)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataSource(ABC):
    """Una fuente expone herramientas (tools) que Claude puede invocar.

    Los nombres de tool deben llevar el prefijo de la fuente (p. ej. ``folio_``)
    para que el registro sepa a qué fuente enrutar cada llamada.
    """

    #: prefijo único, p. ej. "folio"
    name: str

    @abstractmethod
    def tools(self) -> list[dict[str, Any]]:
        """Definiciones de tools en formato Anthropic (name, description, input_schema)."""

    @abstractmethod
    def call(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """Ejecuta una tool y devuelve un resultado serializable a JSON."""


class SourceRegistry:
    def __init__(self, sources: list[DataSource]) -> None:
        self._sources = {s.name: s for s in sources}

    def tools(self) -> list[dict[str, Any]]:
        return [t for s in self._sources.values() for t in s.tools()]

    def call(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        prefix = tool_name.split("_", 1)[0]
        source = self._sources.get(prefix)
        if source is None:
            raise ValueError(f"Tool desconocida: {tool_name}")
        return source.call(tool_name, tool_input)
