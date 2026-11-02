"""¿Qué droguería tiene el medicamento? Arma la lista ordenada por "mejor opción".

Orden (US20240038352A1, recomendación de farmacia):
  1. con unidades suficientes antes que sin stock,
  2. abiertas ahora antes que cerradas,
  3. más cerca primero.
"""

import sqlite3

from ..config import settings
from ..db import now
from . import geo, hours, stock


def pharmacy_summary(conn: sqlite3.Connection, ph: sqlite3.Row, medication_id: int, lat: float, lng: float, quantity: int = 1) -> dict:
    units = stock.current(conn, ph["id"], medication_id)
    km = geo.distance_km(lat, lng, ph["lat"], ph["lng"])
    open_status = hours.status(hours.week_hours(conn, ph["id"]), now())
    return {
        "id": ph["id"],
        "name": ph["name"],
        "address": ph["address"],
        "neighborhood": ph["neighborhood"],
        "phone": ph["phone"],
        "lat": ph["lat"],
        "lng": ph["lng"],
        "distance_km": round(km, 2),
        "distance_text": geo.distance_text(km),
        "travel_text": geo.travel_text(km),
        "open": open_status["open"],
        "hours_text": open_status["text"],
        "units": units,
        "stock_level": stock.level(units),
        "enough": units >= quantity,
        "verified_at": stock.last_verified(conn, ph["id"], medication_id),
        "restock_date": stock.next_restock(conn, ph["id"], medication_id) if units < quantity else None,
    }


def search(
    conn: sqlite3.Connection,
    medication_id: int,
    lat: float,
    lng: float,
    radius_km: float | None = None,
    quantity: int = 1,
) -> list[dict]:
    radius = radius_km or settings.default_radius_km
    results = [
        pharmacy_summary(conn, ph, medication_id, lat, lng, quantity)
        for ph in conn.execute("SELECT * FROM pharmacies").fetchall()
    ]
    results = [r for r in results if r["distance_km"] <= radius]
    results.sort(key=lambda r: (not r["enough"], not r["open"], r["distance_km"]))
    for i, r in enumerate(results):
        r["best"] = i == 0 and r["enough"] and r["open"]
    return results
