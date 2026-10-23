"""Datos de demostración. Uso (desde biblioselect/backend):  python -m app.seed

Crea un usuario por rol con correos ficticios (@example.edu) y contraseña inexistente: el MVP
usa identidad de desarrollo. No ejecutar contra una base de producción.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .db import Base, User, UserRole
from .workflow import Role

DEMO_USERS: list[tuple[str, str, str | None, list[Role]]] = [
    ("admin@example.edu", "Administrador Demo", None, [Role.ADMIN]),
    ("bibliotecario@example.edu", "Bibliotecario Demo", None, [Role.LIBRARIAN]),
    ("director.programa@example.edu", "Director de Programa Demo", "Facultad de Ingeniería", [Role.PROGRAM_DIRECTOR]),
    ("presupuesto@example.edu", "Responsable Presupuestario Demo", None, [Role.BUDGET_OFFICER]),
    ("adquisiciones@example.edu", "Adquisiciones Demo", None, [Role.ACQUISITIONS]),
    ("auditor@example.edu", "Auditor Demo", None, [Role.AUDITOR]),
    ("docente@example.edu", "Docente Demo", "Facultad de Ingeniería", []),
]


def seed_demo(session: Session) -> int:
    created = 0
    for email, name, faculty, roles in DEMO_USERS:
        if session.scalar(select(User).where(User.email == email)) is not None:
            continue
        user = User(email=email, full_name=name, faculty=faculty, active=True)
        user.roles = [UserRole(role=r.value) for r in roles]
        session.add(user)
        created += 1
    session.commit()
    return created


if __name__ == "__main__":
    url = os.getenv("DATABASE_URL", "sqlite:///./biblioselect.db")
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        print(f"Usuarios demo creados: {seed_demo(session)}")
