"""Reloj de días por etapa (M3).

El tiempo se deriva del historial de transiciones, no de contadores guardados: cada entrada abre
un tramo en su ``to_status`` que dura hasta la entrada siguiente, o hasta ahora si la solicitud
sigue abierta.

- Días en la etapa actual = suma de todos los tramos en ese estado. Volver a un estado reanuda su
  reloj en lugar de reiniciarlo; así ``needs_info`` pausa el reloj de evaluación (decisión D3).
- Modo ``business`` (por defecto, D2): solo cuentan lunes a viernes no festivos.
- Semáforo (D4): verde por debajo del 80 % del plazo, ámbar desde el 80 %, rojo al cumplirse.
"""
from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Literal
from zoneinfo import ZoneInfo

from .workflow import TERMINAL_STATUSES, Status

Level = Literal["green", "amber", "red", "none"]

AMBER_RATIO = 0.8
_SECONDS_PER_DAY = 86400

#: Plazo objetivo (días) por estado. Los estados terminales no tienen reloj.
DEFAULT_SLA_DAYS: dict[str, float] = {
    Status.SUBMITTED: 2,  # recepción
    Status.UNDER_REVIEW: 5,  # evaluación bibliotecaria
    Status.NEEDS_INFO: 5,  # tiempo del solicitante
    Status.RETURNED: 5,  # tiempo del solicitante
    Status.AWAITING_APPROVAL: 5,  # aprobación académica
    Status.PROGRAM_APPROVED: 3,  # validación presupuestaria
    Status.BUDGET_APPROVED: 15,  # adquisición
}


@dataclass(frozen=True)
class ClockSettings:
    business_days: bool = True
    holidays: frozenset[date] = frozenset()
    sla_days: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SLA_DAYS))
    tz: tzinfo = UTC

    @classmethod
    def from_env(cls) -> ClockSettings:
        """Lee BIBLIOSELECT_CLOCK_MODE, BIBLIOSELECT_HOLIDAYS, BIBLIOSELECT_SLA_DAYS y BIBLIOSELECT_TZ."""
        mode = os.getenv("BIBLIOSELECT_CLOCK_MODE", "business").strip().lower()
        if mode not in {"business", "calendar"}:
            raise ValueError("BIBLIOSELECT_CLOCK_MODE debe ser 'business' o 'calendar'.")
        holidays = frozenset(
            date.fromisoformat(d.strip()) for d in os.getenv("BIBLIOSELECT_HOLIDAYS", "").split(",") if d.strip()
        )
        sla = dict(DEFAULT_SLA_DAYS)
        for status, days in json.loads(os.getenv("BIBLIOSELECT_SLA_DAYS") or "{}").items():
            sla[Status(status)] = float(days)  # ValueError si el estado no existe
        tz_name = os.getenv("BIBLIOSELECT_TZ")
        return cls(business_days=mode == "business", holidays=holidays, sla_days=sla,
                   tz=ZoneInfo(tz_name) if tz_name else UTC)


@dataclass(frozen=True)
class Segment:
    status: str
    start: datetime
    end: datetime | None  # None = tramo en curso
    days: float


@dataclass(frozen=True)
class Clock:
    status: str
    stage_days: float
    sla_days: float | None
    level: Level
    total_days: float
    running: bool
    business_days: bool


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite devuelve fechas sin zona


def elapsed_days(start: datetime, end: datetime, settings: ClockSettings) -> float:
    start, end = _aware(start).astimezone(UTC), _aware(end).astimezone(UTC)
    if end <= start:
        return 0.0
    if not settings.business_days:
        return (end - start).total_seconds() / _SECONDS_PER_DAY

    total = 0.0
    day = start.astimezone(settings.tz).date()
    last = end.astimezone(settings.tz).date()
    while day <= last:
        if day.weekday() < 5 and day not in settings.holidays:
            day_start = datetime.combine(day, time.min, settings.tz).astimezone(UTC)
            day_end = datetime.combine(day + timedelta(days=1), time.min, settings.tz).astimezone(UTC)
            overlap = (min(end, day_end) - max(start, day_start)).total_seconds()
            if overlap > 0:
                total += overlap
        day += timedelta(days=1)
    return total / _SECONDS_PER_DAY


def segments(entries: Sequence[tuple[str, datetime]], now: datetime, settings: ClockSettings) -> list[Segment]:
    """``entries``: historial ordenado como (estado destino, fecha)."""
    result = []
    for i, (status, start) in enumerate(entries):
        if i + 1 < len(entries):
            end: datetime | None = entries[i + 1][1]
        elif status in TERMINAL_STATUSES:
            end = start  # el reloj se detiene al cerrar
        else:
            end = None
        result.append(Segment(status, start, end, elapsed_days(start, end or now, settings)))
    return result


def level_for(days: float, sla: float | None) -> Level:
    if not sla or sla <= 0:
        return "none"
    ratio = days / sla
    if ratio >= 1:
        return "red"
    if ratio >= AMBER_RATIO:
        return "amber"
    return "green"


def compute_clock(entries: Sequence[tuple[str, datetime]], now: datetime, settings: ClockSettings) -> Clock:
    if not entries:
        raise ValueError("La solicitud no tiene historial.")
    segs = segments(entries, now, settings)
    current = segs[-1].status
    running = current not in TERMINAL_STATUSES
    stage_days = sum(s.days for s in segs if s.status == current) if running else 0.0
    total_days = elapsed_days(segs[0].start, now if running else segs[-1].start, settings)
    sla = settings.sla_days.get(current) if running else None
    return Clock(
        status=current,
        stage_days=stage_days,
        sla_days=sla,
        level=level_for(stage_days, sla),
        total_days=total_days,
        running=running,
        business_days=settings.business_days,
    )
