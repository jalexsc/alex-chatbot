"""API de Alex. Ejecutar:  uvicorn main:app --reload --port 8000  (desde alex-chatbot/backend)"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env")

from agent import Alex  # noqa: E402  (después de load_dotenv)
from sources import SourceRegistry  # noqa: E402
from sources.folio import FolioSource  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

registry = SourceRegistry(
    [
        FolioSource(
            library_name=os.getenv("FOLIO_LIBRARY", "usb"),
            customers_json_path=os.getenv("FOLIO_CUSTOMERS_JSON", str(ROOT / "okapi_customers.json")),
        ),
        # Nuevas fuentes: agregar aquí (p. ej. AlmaSource(...), KohaSource(...))
    ]
)
alex = Alex(registry)

app = FastAPI(title="Alex - Asistente de biblioteca")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALEX_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)


@app.post("/api/chat")
def chat(req: ChatRequest):
    if req.messages[-1].role != "user":
        raise HTTPException(400, "El último mensaje debe ser del usuario.")
    return alex.chat([m.model_dump() for m in req.messages])


@app.get("/api/health")
def health():
    return {"ok": True}
