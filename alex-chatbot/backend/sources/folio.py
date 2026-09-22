"""Fuente FOLIO: reutiliza folio_login_module (sesión por cookies + re-login automático).

Solo lectura y solo datos de inventario/circulación de ítems. No se exponen datos de
usuarios (patrons) para no filtrar información personal al modelo.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

# folio_login_module.py vive en la raíz del proyecto (runenv/)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from folio_login_module import folio_login_module  # noqa: E402

from .base import DataSource  # noqa: E402

MAX_LIMIT = 20


def cql_quote(value: str) -> str:
    """Escapa un valor para usarlo entre comillas dobles en CQL."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("*", "\\*").replace("?", "\\?") + '"'


class FolioSource(DataSource):
    name = "folio"

    def __init__(self, library_name: str, customers_json_path: str) -> None:
        self._library_name = library_name
        self._customers_json_path = customers_json_path
        self._client: folio_login_module | None = None
        self._lock = threading.Lock()  # requests.Session no es del todo thread-safe
        self._locations: dict[str, str] | None = None

    # ---------- infraestructura ----------

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._client is None:  # login perezoso: el server arranca aunque FOLIO esté caído
                self._client = folio_login_module(
                    self._library_name, customers_json_path=self._customers_json_path
                )
            resp = self._client.get(endpoint, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"FOLIO {endpoint} -> {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def _location_name(self, location_id: str | None) -> str | None:
        if not location_id:
            return None
        if self._locations is None:
            data = self._get("/locations", {"limit": 1000})
            self._locations = {loc["id"]: loc.get("name", loc["id"]) for loc in data.get("locations", [])}
        return self._locations.get(location_id, location_id)

    # ---------- tools ----------

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "folio_search_instances",
                "description": (
                    "Busca títulos en el catálogo FOLIO por palabras clave (título, autor, tema, ISBN). "
                    "Devuelve una lista corta con id de instancia, título, contribuyentes, editorial, año y tipo."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Texto a buscar."},
                        "limit": {"type": "integer", "description": f"Máximo de resultados (1-{MAX_LIMIT}).", "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "folio_get_availability",
                "description": (
                    "Dado el id de una instancia (obtenido con folio_search_instances), devuelve sus ejemplares: "
                    "código de barras, signatura topográfica, ubicación y estado (Available, Checked out, etc.)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {"instance_id": {"type": "string", "description": "UUID de la instancia."}},
                    "required": ["instance_id"],
                },
            },
            {
                "name": "folio_find_item_by_barcode",
                "description": "Busca un ejemplar por código de barras y devuelve su estado y ubicación.",
                "input_schema": {
                    "type": "object",
                    "properties": {"barcode": {"type": "string"}},
                    "required": ["barcode"],
                },
            },
        ]

    def call(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        if tool_name == "folio_search_instances":
            return self._search_instances(tool_input["query"], tool_input.get("limit", 10))
        if tool_name == "folio_get_availability":
            return self._availability(tool_input["instance_id"])
        if tool_name == "folio_find_item_by_barcode":
            return self._item_by_barcode(tool_input["barcode"])
        raise ValueError(f"Tool desconocida: {tool_name}")

    # ---------- implementación ----------

    def _search_instances(self, query: str, limit: int) -> dict[str, Any]:
        limit = max(1, min(int(limit), MAX_LIMIT))
        data = self._get(
            "/inventory/instances",
            {"query": f"keywords all {cql_quote(query)}", "limit": limit},
        )
        return {
            "total": data.get("totalRecords", 0),
            "instances": [
                {
                    "id": i["id"],
                    "title": i.get("title"),
                    "contributors": [c.get("name") for c in i.get("contributors", [])][:3],
                    "publisher": [p.get("publisher") for p in i.get("publication", [])][:1],
                    "year": [p.get("dateOfPublication") for p in i.get("publication", [])][:1],
                    "isbn": [
                        x.get("value") for x in i.get("identifiers", []) if "isbn" in str(x.get("identifierTypeId", "")).lower()
                    ][:2],
                }
                for i in data.get("instances", [])
            ],
        }

    def _availability(self, instance_id: str) -> dict[str, Any]:
        holdings = self._get(
            "/holdings-storage/holdings",
            {"query": f"instanceId=={cql_quote(instance_id)}", "limit": 50},
        ).get("holdingsRecords", [])
        if not holdings:
            return {"instance_id": instance_id, "items": [], "note": "Sin holdings registrados."}

        ids = " or ".join(cql_quote(h["id"]) for h in holdings)
        items = self._get(
            "/item-storage/items",
            {"query": f"holdingsRecordId==({ids})", "limit": 100},
        ).get("items", [])
        return {
            "instance_id": instance_id,
            "items": [self._slim_item(i) for i in items],
        }

    def _item_by_barcode(self, barcode: str) -> dict[str, Any]:
        items = self._get(
            "/item-storage/items", {"query": f"barcode=={cql_quote(barcode)}", "limit": 1}
        ).get("items", [])
        if not items:
            return {"found": False}
        return {"found": True, **self._slim_item(items[0])}

    def _slim_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "barcode": item.get("barcode"),
            "call_number": (item.get("itemLevelCallNumber") or item.get("effectiveCallNumberComponents", {}).get("callNumber")),
            "status": (item.get("status") or {}).get("name"),
            "location": self._location_name(item.get("effectiveLocationId") or item.get("permanentLocationId")),
            "copy": item.get("copyNumber"),
            "volume": item.get("volume"),
        }
