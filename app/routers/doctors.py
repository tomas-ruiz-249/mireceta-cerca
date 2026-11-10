"""API de la app del médico (/medico).

El médico busca al paciente por cédula y le emite la fórmula. La fórmula queda en el
mismo sistema: aparece al instante en la app del paciente y la droguería la encuentra
con la cédula, aunque el paciente no use la app.
"""

import sqlite3

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from ..config import settings
from ..db import get_db, transaction
from ..deps import DOCTOR_COOKIE, current_doctor
from ..schemas import PatientIn, PrescriptionCancelIn, PrescriptionIn, StaffLoginIn
from ..services import auth, live, prescriptions as svc, staff, stock
from ..services.medications import to_dict as med_out
from ..services.text import normalize

router = APIRouter(prefix="/api/medico", tags=["médico"])


def _me(d: sqlite3.Row) -> dict:
    return {"id": d["id"], "name": d["name"], "username": d["username"], "specialty": d["specialty"],
            "license": d["license"]}


def _rx_out(conn: sqlite3.Connection, rx: sqlite3.Row, doctor_id: int) -> dict:
    out = svc.view(conn, rx)
    out["mine"] = rx["doctor_id"] == doctor_id
    return out


def _clean(cedula: str) -> str:
    try:
        return auth.clean_cedula(cedula)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))


def _person(conn: sqlite3.Connection, cedula: str, doctor_id: int) -> dict:
    """Una persona puede tener cuenta propia, estar registrada como familiar en la cuenta
    de otra persona (la hija que le maneja la app a la mamá), o las dos cosas."""
    user = conn.execute("SELECT * FROM users WHERE cedula = ?", (cedula,)).fetchone()
    profiles = conn.execute(
        """SELECT p.*, u.first_name, u.last_name, u.pin_hash, u.phone FROM profiles p JOIN users u ON u.id = p.user_id
           WHERE p.cedula = ? ORDER BY p.is_self DESC, p.id""",
        (cedula,),
    ).fetchall()
    if not profiles:
        raise HTTPException(404, "No hay ningún paciente con esa cédula. Puede registrarlo")
    targets = [{
        "profile_id": p["id"],
        "own": bool(p["is_self"]),
        "holder": f"{p['first_name']} {p['last_name']}",
        "relation": None if p["is_self"] else p["relation"],
        "uses_app": bool(p["pin_hash"]),
        "phone": p["phone"],
    } for p in profiles]
    ids = [p["id"] for p in profiles]
    rxs = conn.execute(
        f"SELECT * FROM prescriptions WHERE profile_id IN ({','.join('?' * len(ids))}) ORDER BY issued_at DESC LIMIT 40",
        ids,
    ).fetchall()
    return {
        "cedula": cedula,
        "name": f"{user['first_name']} {user['last_name']}" if user else profiles[0]["name"],
        "targets": targets,
        "prescriptions": [_rx_out(conn, r, doctor_id) for r in rxs],
    }


# --- Ingreso ---

@router.post("/login")
def login(body: StaffLoginIn, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    try:
        did = staff.login(conn, body.username, body.password, kind="doctor")
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    response.set_cookie(DOCTOR_COOKIE, staff.create_session(conn, did, kind="doctor"),
                        max_age=settings.staff_session_hours * 3600,
                        httponly=True, samesite="strict", secure=settings.cookie_secure, path="/")
    return _me(conn.execute("SELECT * FROM doctors WHERE id = ?", (did,)).fetchone())


@router.post("/logout")
def logout(response: Response, conn: sqlite3.Connection = Depends(get_db),
           token: str | None = Cookie(default=None, alias=DOCTOR_COOKIE)):
    staff.end_session(conn, token, kind="doctor")
    response.delete_cookie(DOCTOR_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(d=Depends(current_doctor)):
    return _me(d)


# --- Pacientes ---

@router.get("/patients")
def find_patient(cedula: str = Query(max_length=20), d=Depends(current_doctor),
                 conn: sqlite3.Connection = Depends(get_db)):
    return _person(conn, _clean(cedula), d["id"])


@router.post("/patients")
def add_patient(body: PatientIn, d=Depends(current_doctor), conn: sqlite3.Connection = Depends(get_db)):
    """Paciente nuevo: queda registrado sin PIN, con un código para activar la app después."""
    try:
        with transaction(conn):
            _, code = auth.register_at_pharmacy(conn, body.cedula, body.first_name, body.last_name, body.phone)
    except auth.AuthError as e:
        raise HTTPException(409, str(e))
    out = _person(conn, _clean(body.cedula), d["id"])
    out["activation_code"] = code  # se muestra una sola vez
    return out


# --- Catálogo ---

@router.get("/medications")
def medications(q: str | None = None, d=Depends(current_doctor), conn: sqlite3.Connection = Depends(get_db)):
    """Medicamentos del sistema, con cuántas droguerías lo tienen ahora (para no formular algo agotado)."""
    words = normalize(q).split() if q else []
    where = " AND ".join("search_text LIKE ?" for _ in words) or "1"
    meds = conn.execute(f"SELECT * FROM medications WHERE {where} ORDER BY name LIMIT 20",
                        [f"%{w}%" for w in words]).fetchall()
    pharmacies = [r["id"] for r in conn.execute("SELECT id FROM pharmacies")]
    out = []
    for m in meds:
        have = sum(1 for p in pharmacies if stock.current(conn, p, m["id"]) > 0)
        out.append({**med_out(m), "pharmacies_with_stock": have, "pharmacies_total": len(pharmacies)})
    return out


# --- Fórmulas ---

@router.post("/prescriptions")
def issue(body: PrescriptionIn, d=Depends(current_doctor), conn: sqlite3.Connection = Depends(get_db)):
    try:
        ids = svc.issue(conn, d, body.profile_id, [i.model_dump() for i in body.items], body.valid_days)
    except svc.PrescriptionError as e:
        raise HTTPException(409, str(e))
    rows = conn.execute(f"SELECT * FROM prescriptions WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", ids)
    return [_rx_out(conn, r, d["id"]) for r in rows]


@router.get("/prescriptions")
def mine(d=Depends(current_doctor), conn: sqlite3.Connection = Depends(get_db)):
    """Las fórmulas que emitió este médico, con su estado en vivo (reservada, entregada…)."""
    rows = conn.execute("SELECT * FROM prescriptions WHERE doctor_id = ? ORDER BY issued_at DESC, id DESC LIMIT 100",
                        (d["id"],)).fetchall()
    return [_rx_out(conn, r, d["id"]) for r in rows]


@router.post("/prescriptions/{prescription_id}/cancel")
def cancel(prescription_id: int, body: PrescriptionCancelIn, d=Depends(current_doctor),
           conn: sqlite3.Connection = Depends(get_db)):
    try:
        svc.cancel(conn, prescription_id, d["id"], body.reason)
    except svc.PrescriptionError as e:
        raise HTTPException(409, str(e))
    return _rx_out(conn, conn.execute("SELECT * FROM prescriptions WHERE id = ?", (prescription_id,)).fetchone(), d["id"])


# --- Tiempo real ---

@router.get("/stream")
def stream(request: Request, d=Depends(current_doctor),
           last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    return StreamingResponse(
        live.stream([live.doctor(d["id"])], last_event_id, request.is_disconnected),
        media_type="text/event-stream", headers=live.SSE_HEADERS,
    )
