"""HTTP entry points and ticket persistence."""
import hashlib
import hmac
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from engine import answer

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("uvicorn.error")
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=1200)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]
Queue = Literal["Access & identity", "Software", "Equipment", "IT support"]


class Ask(BaseModel):
    question: Question


class Ticket(BaseModel):
    title: Title
    description: Question
    queue: Queue
    request_id: UUID


def database():
    return closing(sqlite3.connect(os.environ.get("TICKET_DB", str(ROOT / "tickets.sqlite3")), timeout=5))


@asynccontextmanager
async def lifespan(app):
    with database() as conn, conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS tickets (
            request_id TEXT PRIMARY KEY, id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL, description TEXT NOT NULL, queue TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    yield


app = FastAPI(title="ServiceDesk Knowledge", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


def role_for(token):
    if not token:
        return "employee"
    expected = os.getenv("IT_DEMO_TOKEN")
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, "Invalid IT access token.")
    return "it"


def ticket_draft(question):
    lowered = question.lower()
    for queue, hints in (
        ("Access & identity", ("login", "mfa", "password", "sign in", "2fa")),
        ("Software", ("software", "install", "license")),
        ("Equipment", ("laptop", "charger", "monitor")),
    ):
        if any(hint in lowered for hint in hints):
            return {"title": question[:100], "description": question, "queue": queue}
    return {"title": question[:100], "description": question, "queue": "IT support"}


@app.post("/api/ask")
def ask(payload: Ask, x_it_token: Annotated[str | None, Header()] = None):
    role = role_for(x_it_token)
    started = time.perf_counter()
    try:
        result = answer(payload.question, role)
    except httpx.HTTPError:
        result = {"status": "review", "answer": "Knowledge search is temporarily unavailable.",
                  "citation": None, "mode": "unavailable", "usage": None}
    except Exception:
        LOG.error("knowledge_search_failed")
        raise HTTPException(503, "Knowledge search is temporarily unavailable.")
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    usage = result.pop("usage")
    LOG.info("knowledge status=%s mode=%s latency_ms=%s tokens=%s",
             result["status"], result["mode"], elapsed, (usage or {}).get("total_tokens"))
    result.update({"latency_ms": elapsed, "ticket": ticket_draft(payload.question)})
    return result


@app.post("/api/tickets", status_code=201)
def create_ticket(ticket: Ticket):
    request_id = str(ticket.request_id)
    ticket_id = "IT-" + uuid4().hex[:12].upper()
    values = (ticket.title, ticket.description, ticket.queue)
    with database() as conn, conn:
        conn.execute(
            """INSERT INTO tickets (request_id,id,title,description,queue) VALUES (?,?,?,?,?)
               ON CONFLICT(request_id) DO NOTHING""",
            (request_id, ticket_id, *values),
        )
        saved_id, *saved_values = conn.execute(
            "SELECT id,title,description,queue FROM tickets WHERE request_id=?", (request_id,),
        ).fetchone()
        if tuple(saved_values) != values:
            raise HTTPException(409, "This request ID already belongs to a different ticket.")
    LOG.info("ticket id_hash=%s", hashlib.sha256(saved_id.encode()).hexdigest()[:12])
    return {"id": saved_id, "status": "queued"}
