"""Alex: bucle de conversación con Claude + tool use sobre las fuentes registradas."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic

from sources import SourceRegistry

log = logging.getLogger("alex")

MODEL = os.getenv("ALEX_MODEL", "claude-sonnet-5")
MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = """Eres Alex, el asistente virtual de la biblioteca. Ayudas a usuarios y personal \
bibliotecario a encontrar materiales, revisar disponibilidad y resolver dudas sobre el catálogo.

Reglas:
- Responde en el idioma del usuario (por defecto español), con tono cálido, claro y breve.
- Para cualquier dato del catálogo (títulos, ejemplares, estado, ubicación) usa SIEMPRE las herramientas; \
nunca inventes títulos, códigos de barras ni disponibilidad.
- Si la búsqueda no da resultados, dilo y sugiere términos alternativos.
- Cuando muestres ejemplares, indica ubicación, signatura y si están disponibles o prestados.
- Solo puedes consultar información; no puedes hacer préstamos, renovaciones ni modificar registros. \
Si te lo piden, explica que deben acudir al mostrador o al portal de la biblioteca.
- No tienes acceso a datos personales de usuarios; no los solicites ni los inventes.
- Si te piden algo ajeno al ámbito bibliotecario, redirige amablemente."""


class Alex:
    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry
        self._claude = anthropic.Anthropic()  # ANTHROPIC_API_KEY del entorno

    def chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """``messages``: historial [{role, content(str)}]. Devuelve {reply, tools_used}."""
        convo: list[dict[str, Any]] = list(messages)
        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            resp = self._claude.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                tools=self._registry.tools(),
                messages=convo,
            )

            if resp.stop_reason != "tool_use":
                text = "".join(b.text for b in resp.content if b.type == "text")
                return {"reply": text, "tools_used": tools_used}

            convo.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                tools_used.append(block.name)
                try:
                    output = self._registry.call(block.name, block.input)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output, ensure_ascii=False)}
                    )
                except Exception as exc:  # el modelo recibe el error y puede reintentar/explicar
                    log.warning("tool %s falló: %s", block.name, exc)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {exc}", "is_error": True}
                    )
            convo.append({"role": "user", "content": results})

        return {
            "reply": "Lo siento, no pude completar la consulta. ¿Podrías reformular la pregunta?",
            "tools_used": tools_used,
        }
