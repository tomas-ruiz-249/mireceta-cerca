"""Disponibilidad por droguería y avisos de 'cuando llegue'."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import settings
from ..db import get_db, iso, now
from ..deps import current_user
from ..schemas import AlertIn
from ..services import availability, hours, stock

router = APIRouter(prefix="/api", tags=["droguerías"])


def _coords(lat: float | None, lng: float | None) -> tuple[float, float]:
    if lat is None or lng is None:
        return settings.default_lat, settings.default_lng
    return lat, lng


@router.get("/availability")
def search(
    medication_id: int,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = Query(default=None, gt=0, le=50),
    quantity: int = Query(default=1, ge=1, le=10),
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    lat, lng = _coords(lat, lng)
    results = availability.search(conn, medication_id, lat, lng, radius_km, quantity)
    alerts = {r["pharmacy_id"] for r in conn.execute(
        "SELECT pharmacy_id FROM stock_alerts WHERE user_id = ? AND medication_id = ? AND fulfilled_at IS NULL",
        (user["id"], medication_id),
    )}
    for r in results:
        r["alert_set"] = r["id"] in alerts
    return {"used_default_location": lat == settings.default_lat and lng == settings.default_lng, "results": results}


@router.get("/pharmacies/{pharmacy_id}/medications/{medication_id}")
def pharmacy_detail(
    pharmacy_id: int,
    medication_id: int,
    lat: float | None = None,
    lng: float | None = None,
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    ph = conn.execute("SELECT * FROM pharmacies WHERE id = ?", (pharmacy_id,)).fetchone()
    if not ph:
        raise HTTPException(404, "Droguería no encontrada")
    lat, lng = _coords(lat, lng)
    out = availability.pharmacy_summary(conn, ph, medication_id, lat, lng)
    out["pickup_counter"] = ph["pickup_counter"]
    out["pickup_note"] = ph["pickup_note"]
    out["schedule"] = hours.schedule_lines(hours.week_hours(conn, pharmacy_id))
    out["movements"] = stock.movements(conn, pharmacy_id, medication_id)
    out["alert_set"] = bool(conn.execute(
        "SELECT 1 FROM stock_alerts WHERE user_id = ? AND pharmacy_id = ? AND medication_id = ? AND fulfilled_at IS NULL",
        (user["id"], pharmacy_id, medication_id),
    ).fetchone())
    return out


@router.post("/alerts")
def add_alert(body: AlertIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    exists = conn.execute(
        "SELECT 1 FROM stock_alerts WHERE user_id = ? AND pharmacy_id = ? AND medication_id = ? AND fulfilled_at IS NULL",
        (user["id"], body.pharmacy_id, body.medication_id),
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO stock_alerts (user_id, pharmacy_id, medication_id, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], body.pharmacy_id, body.medication_id, iso(now())),
        )
    return {"ok": True}
