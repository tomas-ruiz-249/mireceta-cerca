"""Horarios de atención: ¿está abierta ahora? ¿hasta qué hora?"""

import sqlite3
from datetime import datetime

DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _clock(hhmm: str) -> str:
    """'21:00' -> '9:00 p. m.' (formato usado en Colombia)."""
    if hhmm == "24:00":
        return "medianoche"
    h, m = (int(x) for x in hhmm.split(":"))
    suffix = "a. m." if h < 12 else "p. m."
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def week_hours(conn: sqlite3.Connection, pharmacy_id: int) -> dict[int, tuple[str, str]]:
    rows = conn.execute(
        "SELECT weekday, opens, closes FROM pharmacy_hours WHERE pharmacy_id = ?", (pharmacy_id,)
    ).fetchall()
    return {r["weekday"]: (r["opens"], r["closes"]) for r in rows}


def status(hours: dict[int, tuple[str, str]], at: datetime) -> dict:
    """Devuelve {'open': bool, 'text': 'Abierta hasta 9:00 p. m.'}."""
    today = hours.get(at.weekday())
    minute = at.hour * 60 + at.minute
    if today:
        opens, closes = today
        if opens == "00:00" and closes == "24:00":
            return {"open": True, "text": "Abierta las 24 horas"}
        if _minutes(opens) <= minute < _minutes(closes):
            return {"open": True, "text": f"Abierta hasta las {_clock(closes)}"}
        if minute < _minutes(opens):
            return {"open": False, "text": f"Cerrada. Abre hoy a las {_clock(opens)}"}
    for offset in range(1, 8):
        day = (at.weekday() + offset) % 7
        if day in hours:
            when = "mañana" if offset == 1 else f"el {DAY_NAMES[day]}"
            return {"open": False, "text": f"Cerrada. Abre {when} a las {_clock(hours[day][0])}"}
    return {"open": False, "text": "Cerrada"}


def schedule_lines(hours: dict[int, tuple[str, str]]) -> list[str]:
    lines = []
    for day, name in enumerate(DAY_NAMES):
        if day not in hours:
            lines.append(f"{name.capitalize()}: cerrada")
            continue
        opens, closes = hours[day]
        if opens == "00:00" and closes == "24:00":
            lines.append(f"{name.capitalize()}: 24 horas")
        else:
            lines.append(f"{name.capitalize()}: {_clock(opens)} a {_clock(closes)}")
    return lines
