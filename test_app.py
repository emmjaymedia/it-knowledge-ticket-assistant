import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app import app


class ServiceDeskTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {
            "TICKET_DB": str(Path(directory) / "tickets.sqlite3"),
            "DATABASE_URL": "", "OPENAI_API_KEY": "", "IT_DEMO_TOKEN": "test-it-token",
        }))
        self.client = self.enterContext(TestClient(app))

    def ask(self, question, **kwargs):
        return self.client.post("/api/ask", json={"question": question}, **kwargs)

    def test_workspace_and_cited_answer(self):
        self.assertIn("ServiceDesk", self.client.get("/").text)
        self.assertEqual(self.client.get("/static/workspace.js").status_code, 200)
        answer = self.ask("What should I do when the VPN times out?").json()
        self.assertEqual(answer["citation"]["id"], "vpn-1")

    def test_abstention_and_review(self):
        answer = self.ask("Can IT repair a coffee machine?").json()
        self.assertEqual(answer["status"], "review")
        self.assertIsNone(answer["citation"])
        self.assertEqual(answer["ticket"]["queue"], "IT support")

    def test_role_is_applied_to_retrieval(self):
        question = "What is the break-glass recovery drill exercise reference?"
        self.assertIsNone(self.ask(question).json()["citation"])
        self.assertEqual(self.ask(question, headers={"X-IT-Token": "wrong"}).status_code, 401)
        authorized = self.ask(question, headers={"X-IT-Token": "test-it-token"})
        self.assertEqual(authorized.json()["citation"]["id"], "breakglass-1")

    def test_ticket_retry_and_conflict(self):
        draft = self.ask("My laptop will not boot").json()["ticket"]
        payload = {**draft, "request_id": str(uuid4())}
        first = self.client.post("/api/tickets", json=payload)
        retry = self.client.post("/api/tickets", json=payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(first.json()["status"], "queued")
        conflict = self.client.post("/api/tickets", json={**payload, "title": "Different title"})
        self.assertEqual(conflict.status_code, 409)
