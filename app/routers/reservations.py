import io
import sqlite3

import segno
from fastapi import APIRouter, Depends, HTTPException, Response

from ..db import get_db
from ..deps import current_user, own_profile
from ..schemas import ReservationIn
from ..services import prescriptions as rx_svc, reservations as svc

router = APIRouter(prefix="/api/reservations", tags=["reservas"])


def _owned(conn: sqlite3.Connection, user: sqlite3.Row, reservation_id: int) -> None:
    if not conn.execute("SELECT 1 FROM reservations WHERE id = ? AND user_id = ?", (reservation_id, user["id"])).fetchone():
        raise HTTPException(404, "La reserva no existe")


@router.get("")
def list_reservations(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    svc.expire_overdue(conn)
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM reservations WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (user["id"],)
    )]
    return [svc.detail(conn, i) for i in ids]


@router.post("")
def create(body: ReservationIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    own_profile(conn, user, body.profile_id)
    if body.prescription_id is not None:
        rx = conn.execute("SELECT * FROM prescriptions WHERE id = ? AND profile_id = ?",
                          (body.prescription_id, body.profile_id)).fetchone()
        if not rx or rx["medication_id"] != body.medication_id:
            raise HTTPException(400, "La fórmula no corresponde a este medicamento")
        if problem := rx_svc.usable(rx):
            raise HTTPException(409, problem)
    try:
        rid = svc.create(conn, user["id"], body.profile_id, body.pharmacy_id, body.medication_id,
                         body.quantity, body.prescription_id)
    except svc.ReservationError as e:
        raise HTTPException(409, str(e))
    return svc.detail(conn, rid)


@router.get("/{reservation_id}")
def get(reservation_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    _owned(conn, user, reservation_id)
    svc.expire_overdue(conn)
    return svc.detail(conn, reservation_id)


@router.post("/{reservation_id}/arrived")
def arrived(reservation_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    try:
        svc.arrive(conn, reservation_id, user["id"])
    except svc.ReservationError as e:
        raise HTTPException(409, str(e))
    return svc.detail(conn, reservation_id)


@router.post("/{reservation_id}/cancel")
def cancel(reservation_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    try:
        svc.cancel(conn, reservation_id, user["id"])
    except svc.ReservationError as e:
        raise HTTPException(409, str(e))
    return svc.detail(conn, reservation_id)


@router.get("/{reservation_id}/qr.svg")
def qr(reservation_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    _owned(conn, user, reservation_id)
    code = conn.execute("SELECT code FROM reservations WHERE id = ?", (reservation_id,)).fetchone()["code"]
    buf = io.BytesIO()
    segno.make(f"MIRECETA:{code}", error="m").save(buf, kind="svg", scale=8, border=2, xmldecl=False)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=3600"})
