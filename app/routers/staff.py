"""API de la app del dispensador (personal de la droguería).

Toda ruta está limitada a la droguería de la persona que ingresó: nadie ve ni
toca reservas o inventario de otra droguería.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from ..config import settings
from ..db import get_db, now, parse, transaction
from ..deps import STAFF_COOKIE, current_staff
from ..schemas import (
    AdvanceIn, DeliverIn, PatientIn, RestockIn, StaffCancelIn, StaffLoginIn, StaffReservationIn, StockMoveIn,
)
from ..services import auth, live, prescriptions as rx_svc, reservations as svc, staff, stock
from ..services.medications import to_dict as med_out

router = APIRouter(prefix="/api/personal", tags=["dispensador"])

ACTIVE = ("recibida", "en_preparacion", "lista")


def _me(conn: sqlite3.Connection, s: sqlite3.Row) -> dict:
    ph = conn.execute("SELECT * FROM pharmacies WHERE id = ?", (s["pharmacy_id"],)).fetchone()
    return {
        "id": s["id"], "name": s["name"], "username": s["username"],
        "pharmacy": {"id": ph["id"], "name": ph["name"], "address": ph["address"],
                     "pickup_counter": ph["pickup_counter"]},
    }


def _own(conn: sqlite3.Connection, s: sqlite3.Row, reservation_id: int) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM reservations WHERE id = ? AND pharmacy_id = ?",
                     (reservation_id, s["pharmacy_id"])).fetchone()
    if not r:
        raise HTTPException(404, "La reserva no existe en esta droguería")
    return r


def _view(conn: sqlite3.Connection, s: sqlite3.Row, reservation_id: int) -> dict:
    return svc.staff_view(conn, _own(conn, s, reservation_id))


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (svc.ReservationError, stock.StockError, auth.AuthError) as e:
        raise HTTPException(409, str(e))


# --- Ingreso ---

@router.post("/login")
def login(body: StaffLoginIn, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    try:
        sid = staff.login(conn, body.username, body.password)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    response.set_cookie(STAFF_COOKIE, staff.create_session(conn, sid), max_age=settings.staff_session_hours * 3600,
                        httponly=True, samesite="strict", secure=settings.cookie_secure, path="/")
    return _me(conn, conn.execute("SELECT * FROM staff WHERE id = ?", (sid,)).fetchone())


@router.post("/logout")
def logout(response: Response, conn: sqlite3.Connection = Depends(get_db),
           token: str | None = Cookie(default=None, alias=STAFF_COOKIE)):
    staff.end_session(conn, token)
    response.delete_cookie(STAFF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    return _me(conn, s)


# --- Pedidos ---

@router.get("/reservations")
def queue(s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    """Pedidos en curso y lo entregado o cerrado hoy."""
    svc.expire_overdue(conn)
    rows = conn.execute(
        f"""SELECT * FROM reservations WHERE pharmacy_id = ? AND status IN ({",".join("?" * len(ACTIVE))})
            ORDER BY created_at""",
        (s["pharmacy_id"], *ACTIVE),
    ).fetchall()
    today = now().date().isoformat()
    closed = conn.execute(
        """SELECT * FROM reservations WHERE pharmacy_id = ? AND status IN ('retirada', 'cancelada', 'vencida')
           AND substr(updated_at, 1, 10) = ? ORDER BY updated_at DESC LIMIT 40""",
        (s["pharmacy_id"], today),
    ).fetchall()
    return {
        "active": [svc.staff_view(conn, r) for r in rows],
        "closed_today": [svc.staff_view(conn, r) for r in closed],
        "last_event": live.latest_id(conn),
    }


@router.get("/reservations/by-code/{code}")
def by_code(code: str, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    """El dispensador digita o escanea el código que muestra el paciente."""
    r = _run(svc.find_by_code, conn, code, s["pharmacy_id"])
    return svc.staff_view(conn, r)


@router.get("/reservations/{reservation_id}")
def one(reservation_id: int, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    return _view(conn, s, reservation_id)


@router.post("/reservations/{reservation_id}/advance")
def advance(reservation_id: int, body: AdvanceIn, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    _run(svc.advance, conn, reservation_id, s["pharmacy_id"], s["name"], body.expected)
    return _view(conn, s, reservation_id)


@router.post("/reservations/{reservation_id}/deliver")
def deliver(reservation_id: int, body: DeliverIn, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    _run(svc.deliver, conn, reservation_id, s["pharmacy_id"], body.code, s["name"])
    return _view(conn, s, reservation_id)


@router.post("/reservations/{reservation_id}/cancel")
def cancel(reservation_id: int, body: StaffCancelIn, s=Depends(current_staff),
           conn: sqlite3.Connection = Depends(get_db)):
    _run(svc.cancel_by_pharmacy, conn, reservation_id, s["pharmacy_id"], body.reason, s["name"])
    return _view(conn, s, reservation_id)


# --- Inventario ---

@router.get("/stock")
def stock_list(q: str | None = None, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    from ..services.text import normalize

    words = normalize(q).split() if q else []
    where = " AND ".join("search_text LIKE ?" for _ in words) or "1"
    meds = conn.execute(f"SELECT * FROM medications WHERE {where} ORDER BY name", [f"%{w}%" for w in words]).fetchall()
    pid = s["pharmacy_id"]
    reserved = {r["medication_id"]: r["n"] for r in conn.execute(
        f"""SELECT medication_id, SUM(quantity) AS n FROM reservations
            WHERE pharmacy_id = ? AND status IN ({",".join("?" * len(ACTIVE))}) GROUP BY medication_id""",
        (pid, *ACTIVE),
    )}
    out = []
    for m in meds:
        units = stock.current(conn, pid, m["id"])
        out.append({
            "medication": med_out(m),
            "units": units,                       # disponibles para nuevas reservas
            "reserved": reserved.get(m["id"], 0),  # apartadas, todavía en el estante
            "level": stock.level(units),
            "verified_at": stock.last_verified(conn, pid, m["id"]),
            "restock_date": stock.next_restock(conn, pid, m["id"]),
            "movements": stock.movements(conn, pid, m["id"], limit=5),
        })
    out.sort(key=lambda x: ({"none": 0, "low": 1, "ok": 2}[x["level"]], x["medication"]["name"]))
    return out


@router.post("/stock")
def stock_move(body: StockMoveIn, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    if body.kind not in ("ingreso", "venta", "ajuste", "conteo"):
        raise HTTPException(400, "Tipo de movimiento no permitido")
    delta = body.delta
    if body.kind == "ingreso":
        delta = abs(delta)
    elif body.kind == "venta":
        delta = -abs(delta)
    elif body.kind == "conteo":
        delta = 0
    if delta == 0 and body.kind != "conteo":
        raise HTTPException(400, "Escriba cuántas cajas")
    if not conn.execute("SELECT 1 FROM medications WHERE id = ?", (body.medication_id,)).fetchone():
        raise HTTPException(404, "Medicamento no encontrado")

    def apply():
        with transaction(conn):
            return stock.add_movement(conn, s["pharmacy_id"], body.medication_id, delta, body.kind,
                                      note=body.note or f"Registrado por {s['name']}",
                                      scanned=body.scanned or body.kind == "conteo")

    return {"units": _run(apply)}


@router.post("/restocks")
def restock(body: RestockIn, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    try:
        when = date.fromisoformat(body.expected_date)
    except ValueError:
        raise HTTPException(400, "Fecha no válida")
    if when < now().date():
        raise HTTPException(400, "La fecha ya pasó")
    with transaction(conn):
        conn.execute("INSERT INTO restocks (pharmacy_id, medication_id, expected_date, quantity) VALUES (?, ?, ?, ?)",
                     (s["pharmacy_id"], body.medication_id, body.expected_date, body.quantity))
        live.emit(conn, live.pharmacy(s["pharmacy_id"]), "stock", body.medication_id)
    return {"ok": True}


# --- Atención a pacientes sin la app (mostrador o teléfono) ---

def _patient_out(conn: sqlite3.Connection, user: sqlite3.Row) -> dict:
    profiles = conn.execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY is_self DESC, id", (user["id"],)).fetchall()
    out = []
    for p in profiles:
        rxs = conn.execute(
            """SELECT p.*, m.name, m.strength, m.presentation, m.image FROM prescriptions p
               JOIN medications m ON m.id = p.medication_id
               WHERE p.profile_id = ? AND p.dispensed_at IS NULL AND p.cancelled_at IS NULL
               ORDER BY p.expires_at""",
            (p["id"],),
        ).fetchall()
        out.append({
            "id": p["id"], "name": p["name"], "relation": p["relation"], "is_self": bool(p["is_self"]),
            "prescriptions": [{
                "id": r["id"], "code": r["code"], "prescriber": r["prescriber"], "quantity": r["quantity"],
                "expires_at": r["expires_at"], "valid": parse(r["expires_at"]) >= now(),
                "medication": med_out({**dict(r), "id": r["medication_id"]}),
            } for r in rxs],
        })
    return {
        "id": user["id"], "name": f"{user['first_name']} {user['last_name']}", "phone": user["phone"],
        "uses_app": bool(user["pin_hash"]), "profiles": out,
    }


@router.get("/patients")
def find_patient(cedula: str = Query(max_length=20), s=Depends(current_staff),
                 conn: sqlite3.Connection = Depends(get_db)):
    try:
        ced = auth.clean_cedula(cedula)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    user = conn.execute("SELECT * FROM users WHERE cedula = ?", (ced,)).fetchone()
    if not user:
        # Puede ser un familiar registrado en la cuenta de otra persona.
        prof = conn.execute("SELECT user_id FROM profiles WHERE cedula = ? ORDER BY is_self DESC LIMIT 1", (ced,)).fetchone()
        if prof:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (prof["user_id"],)).fetchone()
    if not user:
        raise HTTPException(404, "No hay ningún paciente con esa cédula. Puede registrarlo")
    return _patient_out(conn, user)


@router.post("/patients")
def add_patient(body: PatientIn, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    try:
        with transaction(conn):
            uid, code = auth.register_at_pharmacy(conn, body.cedula, body.first_name, body.last_name, body.phone)
    except auth.AuthError as e:
        raise HTTPException(409, str(e))
    out = _patient_out(conn, conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())
    out["activation_code"] = code  # se muestra una sola vez para anotárselo al paciente
    return out


@router.post("/reservations")
def reserve_for_patient(body: StaffReservationIn, s=Depends(current_staff), conn: sqlite3.Connection = Depends(get_db)):
    profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (body.profile_id,)).fetchone()
    if not profile:
        raise HTTPException(404, "Paciente no encontrado")
    if body.prescription_id is not None:
        rx = conn.execute("SELECT * FROM prescriptions WHERE id = ? AND profile_id = ?",
                          (body.prescription_id, body.profile_id)).fetchone()
        if not rx or rx["medication_id"] != body.medication_id:
            raise HTTPException(400, "La fórmula no corresponde a este medicamento")
        if problem := rx_svc.usable(rx):
            raise HTTPException(409, problem)
    rid = _run(svc.create, conn, profile["user_id"], profile["id"], s["pharmacy_id"], body.medication_id,
               body.quantity, body.prescription_id, s)
    return _view(conn, s, rid)


# --- Tiempo real ---

@router.get("/stream")
def stream(request: Request, s=Depends(current_staff),
           last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    """Eventos en vivo de esta droguería: reserva nueva, paciente que llegó, cambios de stock."""
    return StreamingResponse(
        live.stream([live.pharmacy(s["pharmacy_id"])], last_event_id, request.is_disconnected,
                    housekeeping=svc.expire_overdue),
        media_type="text/event-stream", headers=live.SSE_HEADERS,
    )
