from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.clock import ClockSettings, compute_clock, elapsed_days, level_for, segments
from app.db import WorkflowEntry
from app.main import create_app
from app.seed import seed_demo
from conftest import VALID_REQUEST, as_user

CALENDAR = ClockSettings(business_days=False)
BUSINESS = ClockSettings(business_days=True)
FRI_NOON = datetime(2026, 10, 23, 12, tzinfo=UTC)  # viernes
MON_NOON = datetime(2026, 10, 26, 12, tzinfo=UTC)  # lunes siguiente


def at(days: float) -> datetime:
    return datetime(2026, 10, 19, tzinfo=UTC) + timedelta(days=days)  # lunes 00:00


# ---------- cálculo de días ----------

def test_calendar_days_are_fractional():
    assert elapsed_days(at(0), at(2.5), CALENDAR) == pytest.approx(2.5)


def test_business_days_skip_weekend():
    # Medio viernes + medio lunes; sábado y domingo no cuentan.
    assert elapsed_days(FRI_NOON, MON_NOON, BUSINESS) == pytest.approx(1.0)
    assert elapsed_days(FRI_NOON, MON_NOON, CALENDAR) == pytest.approx(3.0)


def test_business_days_skip_holidays():
    settings = ClockSettings(business_days=True, holidays=frozenset({date(2026, 10, 20)}))
    assert elapsed_days(at(0), at(3), settings) == pytest.approx(2.0)  # lunes y miércoles


def test_naive_datetimes_are_treated_as_utc():
    naive = datetime(2026, 10, 19)
    assert elapsed_days(naive, at(1), CALENDAR) == pytest.approx(1.0)


def test_end_before_start_is_zero():
    assert elapsed_days(at(2), at(1), CALENDAR) == 0.0


# ---------- semáforo ----------

@pytest.mark.parametrize(
    ("days", "level"),
    [(0, "green"), (3.9, "green"), (4.0, "amber"), (4.99, "amber"), (5.0, "red"), (9, "red")],
)
def test_level_thresholds(days, level):
    assert level_for(days, 5) == level


def test_level_without_sla_is_none():
    assert level_for(3, None) == "none"


# ---------- reloj de una solicitud ----------

def test_needs_info_pauses_review_clock():
    entries = [
        ("submitted", at(0)),
        ("under_review", at(1)),
        ("needs_info", at(3)),  # 2 días en evaluación
        ("under_review", at(6)),  # 3 días esperando al solicitante
    ]
    clock = compute_clock(entries, at(7), CALENDAR)
    assert clock.status == "under_review"
    assert clock.stage_days == pytest.approx(3.0)  # 2 + 1, no 1
    assert clock.total_days == pytest.approx(7.0)
    assert clock.sla_days == 5
    assert clock.level == "green"
    assert clock.running


def test_clock_turns_amber_and_red():
    entries = [("submitted", at(0)), ("under_review", at(1))]
    assert compute_clock(entries, at(5), CALENDAR).level == "amber"  # 4 de 5
    assert compute_clock(entries, at(6), CALENDAR).level == "red"  # 5 de 5


def test_terminal_status_stops_clock():
    entries = [("submitted", at(0)), ("under_review", at(1)), ("rejected", at(3))]
    clock = compute_clock(entries, at(30), CALENDAR)
    assert not clock.running
    assert clock.level == "none"
    assert clock.total_days == pytest.approx(3.0)  # congelado al cerrar


def test_segments_report_each_stage_duration():
    entries = [("submitted", at(0)), ("under_review", at(1)), ("awaiting_approval", at(4))]
    segs = segments(entries, at(6), CALENDAR)
    assert [round(s.days, 1) for s in segs] == [1.0, 3.0, 2.0]
    assert [s.end is None for s in segs] == [False, False, True]


def test_empty_history_raises():
    with pytest.raises(ValueError):
        compute_clock([], at(0), CALENDAR)


# ---------- configuración ----------

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("BIBLIOSELECT_CLOCK_MODE", "calendar")
    monkeypatch.setenv("BIBLIOSELECT_HOLIDAYS", "2026-12-25, 2027-01-01")
    monkeypatch.setenv("BIBLIOSELECT_SLA_DAYS", '{"under_review": 7}')
    settings = ClockSettings.from_env()
    assert not settings.business_days
    assert settings.holidays == {date(2026, 12, 25), date(2027, 1, 1)}
    assert settings.sla_days["under_review"] == 7
    assert settings.sla_days["awaiting_approval"] == 5  # el resto conserva su valor


@pytest.mark.parametrize(
    ("var", "value"),
    [("BIBLIOSELECT_CLOCK_MODE", "weekly"), ("BIBLIOSELECT_SLA_DAYS", '{"no_existe": 3}')],
)
def test_invalid_settings_fail_fast(monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(ValueError):
        ClockSettings.from_env()


# ---------- API ----------

@pytest.fixture()
def calendar_client(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'clock.db'}", dev_auth=True, clock_settings=CALENDAR)
    with app.state.session_factory() as session:
        seed_demo(session)
    return TestClient(app)


def backdate(client: TestClient, request_id: str, days: float) -> None:
    """Desplaza todo el historial de la solicitud ``days`` días hacia el pasado."""
    with client.app.state.session_factory() as session:
        for entry in session.query(WorkflowEntry).filter_by(request_id=request_id):
            entry.created_at = entry.created_at - timedelta(days=days)
        session.commit()


def test_new_request_shows_green_running_clock(calendar_client):
    data = calendar_client.post("/api/requests", json=VALID_REQUEST, headers=as_user("docente@example.edu")).json()
    assert data["clock"] == {
        "status": "submitted",
        "stage_days": 0.0,
        "sla_days": 2,
        "level": "green",
        "total_days": 0.0,
        "running": True,
        "mode": "calendar",
    }


def test_clock_in_inbox_detail_and_history(calendar_client):
    headers = as_user("docente@example.edu")
    rid = calendar_client.post("/api/requests", json=VALID_REQUEST, headers=headers).json()["id"]
    backdate(calendar_client, rid, 3)  # 3 días en "submitted" con plazo de 2 → rojo

    detail = calendar_client.get(f"/api/requests/{rid}", headers=headers).json()
    assert detail["clock"]["level"] == "red"
    assert detail["clock"]["stage_days"] == pytest.approx(3.0, abs=0.1)

    inbox = calendar_client.get("/api/requests", headers=as_user("bibliotecario@example.edu")).json()
    assert inbox[0]["clock"]["level"] == "red"

    calendar_client.post(
        f"/api/requests/{rid}/transitions", json={"action": "start_review"},
        headers=as_user("bibliotecario@example.edu"),
    )
    hist = calendar_client.get(f"/api/requests/{rid}/history", headers=headers).json()
    assert hist[0]["duration_days"] == pytest.approx(3.0, abs=0.1)
    assert not hist[0]["open"]
    assert hist[1]["open"]

    # La nueva etapa arranca en verde: cada estado tiene su propio reloj.
    detail = calendar_client.get(f"/api/requests/{rid}", headers=headers).json()
    assert detail["clock"]["status"] == "under_review"
    assert detail["clock"]["level"] == "green"
    assert detail["clock"]["total_days"] == pytest.approx(3.0, abs=0.1)


def test_cancelled_request_has_stopped_clock(calendar_client):
    headers = as_user("docente@example.edu")
    rid = calendar_client.post("/api/requests", json=VALID_REQUEST, headers=headers).json()["id"]
    data = calendar_client.post(f"/api/requests/{rid}/cancel", json={"reason": "Ya no se necesita"}, headers=headers).json()
    assert data["clock"]["running"] is False
    assert data["clock"]["level"] == "none"
