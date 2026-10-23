from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.db import User, UserRole  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed_demo  # noqa: E402
from app.workflow import Role  # noqa: E402

VALID_REQUEST = {
    "title": "Introducción a la teoría de grafos",
    "material_type": "print_book",
    "isbn": "978-0-306-40615-7",
    "authors": "Autor Ficticio",
    "requester_name": "Docente Demo",
    "requester_email": "docente@example.edu",
    "faculty": "Facultad de Ingeniería",
    "program": "Ingeniería de Sistemas",
    "justification": "Bibliografía obligatoria del curso de algoritmos de la segunda unidad.",
    "quantity": 2,
}


@pytest.fixture()
def app_client(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'test.db'}", dev_auth=True)
    with app.state.session_factory() as session:
        seed_demo(session)
    return TestClient(app)


@pytest.fixture()
def db_session(app_client):
    with app_client.app.state.session_factory() as session:
        yield session


def as_user(email: str) -> dict[str, str]:
    return {"X-Dev-User": email}


@pytest.fixture()
def make_user(db_session: Session):
    def _make(email: str, roles: list[Role], faculty: str | None = None) -> User:
        user = User(email=email, full_name=email, faculty=faculty, active=True)
        user.roles = [UserRole(role=r.value) for r in roles]
        db_session.add(user)
        db_session.commit()
        return user

    return _make
