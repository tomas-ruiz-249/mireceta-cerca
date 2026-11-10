"""Ciclo de vida de una reserva.

    recibida -> en_preparacion -> lista -> retirada
        \\______________\\_________\\-> cancelada (paciente o droguería) / vencida (no la recogió a tiempo)

Al crear la reserva se aparta el stock (movimiento 'reserva'); si se cancela
o vence, se devuelve (movimiento 'liberacion'). Así el número que ven los
demás pacientes nunca incluye cajas ya apartadas.

Cada cambio emite un evento en vivo para la droguería y para el paciente
(services/live.py), así las dos aplicaciones se actualizan al instante.
"""

import secrets
import sqlite3
from datetime import timedelta

from ..config import settings
from ..db import iso, now, parse, transaction
from . import live, medications, prescriptions, stock
from .notify import notify

STEPS = ["recibida", "en_preparacion", "lista", "retirada"]
CLOSED = {"retirada", "cancelada", "vencida"}
LABELS = {
    "recibida": "Reserva recibida",
    "en_preparacion": "En preparación",
    "lista": "Lista para recoger",
    "retirada": "Entregada",
    "cancelada": "Cancelada",
    "vencida": "Vencida",
}
# Sin 0/O ni 1/I/L: códigos fáciles de leer en voz alta en el mostrador.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


class ReservationError(Exception):
    pass


def _new_code(conn: sqlite3.Connection) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
        if not conn.execute("SELECT 1 FROM reservations WHERE code = ?", (code,)).fetchone():
            return code


def clean_code(code: str) -> str:
    """Acepta '7f3k', ' 7F3K ' o el contenido del QR 'MIRECETA:7F3K'."""
    code = (code or "").strip().upper()
    if code.startswith("MIRECETA:"):
        code = code.split(":", 1)[1]
    return code.replace(" ", "")


def _event(conn: sqlite3.Connection, reservation_id: int, text: str, actor: str | None = None) -> None:
    conn.execute(
        "INSERT INTO reservation_events (reservation_id, text, actor, created_at) VALUES (?, ?, ?, ?)",
        (reservation_id, text, actor, iso(now())),
    )


def _broadcast(conn: sqlite3.Connection, r: sqlite3.Row, kind: str = "reservation") -> None:
    live.emit(conn, live.pharmacy(r["pharmacy_id"]), kind, r["id"])
    live.emit(conn, live.user(r["user_id"]), kind, r["id"])
    prescriptions.broadcast_to_doctor(conn, r["prescription_id"])


def _get(conn: sqlite3.Connection, reservation_id: int, pharmacy_id: int | None = None) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
    if not row or (pharmacy_id is not None and row["pharmacy_id"] != pharmacy_id):
        raise ReservationError("La reserva no existe")
    return row


def _context(conn: sqlite3.Connection, r: sqlite3.Row) -> tuple[sqlite3.Row, sqlite3.Row]:
    ph = conn.execute("SELECT * FROM pharmacies WHERE id = ?", (r["pharmacy_id"],)).fetchone()
    med = conn.execute("SELECT * FROM medications WHERE id = ?", (r["medication_id"],)).fetchone()
    return ph, med


def _set_status(conn: sqlite3.Connection, r: sqlite3.Row, status: str) -> None:
    conn.execute("UPDATE reservations SET status = ?, updated_at = ? WHERE id = ?", (status, iso(now()), r["id"]))
    _broadcast(conn, r)


def create(
    conn: sqlite3.Connection,
    user_id: int,
    profile_id: int,
    pharmacy_id: int,
    medication_id: int,
    quantity: int = 1,
    prescription_id: int | None = None,
    staff: sqlite3.Row | None = None,
) -> int:
    """Crea la reserva. `staff`: la hizo el personal en el mostrador o por teléfono."""
    if quantity < 1:
        raise ReservationError("La cantidad debe ser al menos 1")
    with transaction(conn):
        open_dup = conn.execute(
            f"""SELECT 1 FROM reservations WHERE profile_id = ? AND medication_id = ?
                AND status NOT IN ({','.join('?' * len(CLOSED))})""",
            (profile_id, medication_id, *CLOSED),
        ).fetchone()
        if open_dup:
            raise ReservationError("Ya tiene una reserva activa de este medicamento")
        if stock.current(conn, pharmacy_id, medication_id) < quantity:
            raise ReservationError("La droguería ya no tiene unidades suficientes")
        t = now()
        cur = conn.execute(
            """INSERT INTO reservations
               (code, user_id, profile_id, prescription_id, pharmacy_id, medication_id, quantity,
                status, ready_estimate, hold_until, created_by_staff, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'recibida', ?, ?, ?, ?, ?)""",
            (
                _new_code(conn), user_id, profile_id, prescription_id, pharmacy_id, medication_id, quantity,
                iso(t + timedelta(minutes=settings.preparation_minutes)),
                iso(t + timedelta(hours=settings.reservation_hold_hours)),
                staff["id"] if staff else None,
                iso(t), iso(t),
            ),
        )
        rid = cur.lastrowid
        stock.add_movement(conn, pharmacy_id, medication_id, -quantity, "reserva", reservation_id=rid)
        ph = conn.execute("SELECT name FROM pharmacies WHERE id = ?", (pharmacy_id,)).fetchone()
        if staff:
            _event(conn, rid, f"{ph['name']} tomó su reserva en el mostrador o por teléfono", staff["name"])
        else:
            _event(conn, rid, f"{ph['name']} recibió su reserva")
        _broadcast(conn, _get(conn, rid), "new_reservation")
    return rid


def advance(
    conn: sqlite3.Connection,
    reservation_id: int,
    pharmacy_id: int | None = None,
    actor: str | None = None,
    expected: str | None = None,
) -> str:
    """Pasa al siguiente paso. Lo usa la droguería.

    `expected`: el estado que la persona veía en pantalla. Si otra persona ya avanzó
    la reserva (dos dispensadores a la vez), se rechaza en lugar de saltarse un paso.
    """
    with transaction(conn):
        r = _get(conn, reservation_id, pharmacy_id)
        if r["status"] in CLOSED:
            raise ReservationError(f"La reserva ya está {LABELS[r['status']].lower()}")
        if expected and r["status"] != expected:
            raise ReservationError(f"Otra persona ya la pasó a «{LABELS[r['status']]}»")
        nxt = STEPS[STEPS.index(r["status"]) + 1]
        if nxt == "retirada":
            raise ReservationError("Para entregar, confirme el código del paciente")
        ph, med = _context(conn, r)
        _set_status(conn, r, nxt)
        if nxt == "en_preparacion":
            _event(conn, r["id"], "El farmacéutico revisó la fórmula y está preparando el pedido", actor)
        elif nxt == "lista":
            _event(conn, r["id"], f"Pedido escaneado y listo en {ph['pickup_counter']}", actor)
            notify(
                conn, r["user_id"], "Su medicamento está listo",
                f"{med['name']} {med['strength']} · {ph['name']} · Recójalo en {ph['pickup_counter']}. "
                f"Código: {r['code']}",
                f"#/reserva/{r['id']}",
            )
    return nxt


def _deliver(conn: sqlite3.Connection, r: sqlite3.Row, actor: str | None = None) -> None:
    _set_status(conn, r, "retirada")
    _event(conn, r["id"], "Medicamento entregado", actor)
    if r["prescription_id"]:
        conn.execute("UPDATE prescriptions SET dispensed_at = ? WHERE id = ?", (iso(now()), r["prescription_id"]))


def find_by_code(conn: sqlite3.Connection, code: str, pharmacy_id: int | None = None) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM reservations WHERE code = ?", (clean_code(code),)).fetchone()
    if not row or (pharmacy_id is not None and row["pharmacy_id"] != pharmacy_id):
        raise ReservationError("No hay ninguna reserva con ese código en esta droguería")
    return row


def pickup_by_code(conn: sqlite3.Connection, code: str, pharmacy_id: int | None = None, actor: str | None = None) -> int:
    """El mostrador escanea o digita el código del paciente y entrega."""
    with transaction(conn):
        row = find_by_code(conn, code, pharmacy_id)
        if row["status"] != "lista":
            raise ReservationError(f"La reserva está «{LABELS[row['status']]}», no lista para entregar")
        _deliver(conn, row, actor)
    return row["id"]


def deliver(conn: sqlite3.Connection, reservation_id: int, pharmacy_id: int, code: str, actor: str | None = None) -> None:
    """Entrega desde la tarjeta de la reserva: el código del paciente debe coincidir."""
    with transaction(conn):
        r = _get(conn, reservation_id, pharmacy_id)
        if clean_code(code) != r["code"]:
            raise ReservationError("El código no coincide con esta reserva. Pídale al paciente que lo muestre de nuevo")
        if r["status"] != "lista":
            raise ReservationError(f"La reserva está «{LABELS[r['status']]}», no lista para entregar")
        _deliver(conn, r, actor)


def arrive(conn: sqlite3.Connection, reservation_id: int, user_id: int) -> None:
    """'Ya llegué': reemplaza en la web la detección por beacon de US10430556B2."""
    with transaction(conn):
        r = _get(conn, reservation_id)
        if r["user_id"] != user_id:
            raise ReservationError("La reserva no existe")
        if r["status"] in CLOSED:
            raise ReservationError("La reserva ya está cerrada")
        if r["arrived_at"]:
            return
        conn.execute("UPDATE reservations SET arrived_at = ?, updated_at = ? WHERE id = ?", (iso(now()), iso(now()), r["id"]))
        _event(conn, r["id"], "Usted avisó que llegó a la droguería")
        _broadcast(conn, r, "arrived")


def cancel(conn: sqlite3.Connection, reservation_id: int, user_id: int | None) -> None:
    """Cancelación por el paciente (o por la terminal si user_id es None)."""
    with transaction(conn):
        r = _get(conn, reservation_id)
        if user_id is not None and r["user_id"] != user_id:
            raise ReservationError("La reserva no existe")
        if r["status"] in CLOSED:
            raise ReservationError("La reserva ya está cerrada")
        _release(conn, r, "cancelada", "Reserva cancelada")


def cancel_by_pharmacy(conn: sqlite3.Connection, reservation_id: int, pharmacy_id: int, reason: str, actor: str) -> None:
    """La droguería no puede entregar (caja dañada, fórmula con problemas…). Se avisa al paciente."""
    reason = (reason or "").strip()
    if not reason:
        raise ReservationError("Escriba el motivo para que el paciente lo entienda")
    with transaction(conn):
        r = _get(conn, reservation_id, pharmacy_id)
        if r["status"] in CLOSED:
            raise ReservationError("La reserva ya está cerrada")
        _release(conn, r, "cancelada", f"La droguería canceló la reserva: {reason}", actor)
        ph, med = _context(conn, r)
        notify(conn, r["user_id"], "La droguería canceló su reserva",
               f"{med['name']} en {ph['name']}: {reason}. Puede reservar en otra droguería.",
               f"#/medicamento/{med['id']}")


def _release(conn: sqlite3.Connection, r: sqlite3.Row, status: str, text: str, actor: str | None = None) -> None:
    _set_status(conn, r, status)
    stock.add_movement(conn, r["pharmacy_id"], r["medication_id"], r["quantity"], "liberacion", reservation_id=r["id"])
    _event(conn, r["id"], text, actor)


def expire_overdue(conn: sqlite3.Connection) -> int:
    """Devuelve al stock las reservas no retiradas a tiempo. Se llama al consultar reservas."""
    overdue = conn.execute(
        f"SELECT * FROM reservations WHERE status NOT IN ({','.join('?' * len(CLOSED))}) AND hold_until < ?",
        (*CLOSED, iso(now())),
    ).fetchall()
    for r in overdue:
        with transaction(conn):
            fresh = _get(conn, r["id"])
            if fresh["status"] in CLOSED:
                continue
            _release(conn, fresh, "vencida", "La reserva venció porque no se recogió a tiempo")
            ph, med = _context(conn, fresh)
            notify(conn, fresh["user_id"], "Su reserva venció",
                   f"No se recogió {med['name']} en {ph['name']}. Puede reservar de nuevo.", "#/buscar")
    return len(overdue)


def detail(conn: sqlite3.Connection, reservation_id: int) -> dict:
    r = _get(conn, reservation_id)
    ph, med = _context(conn, r)
    profile = conn.execute("SELECT name FROM profiles WHERE id = ?", (r["profile_id"],)).fetchone()
    events = conn.execute(
        "SELECT text, created_at FROM reservation_events WHERE reservation_id = ? ORDER BY created_at, id", (r["id"],)
    ).fetchall()
    step = STEPS.index(r["status"]) if r["status"] in STEPS else None
    return {
        "id": r["id"],
        "code": r["code"],
        "status": r["status"],
        "status_label": LABELS[r["status"]],
        "step": step,
        "steps": [LABELS[s] for s in STEPS],
        "active": r["status"] not in CLOSED,
        "quantity": r["quantity"],
        "for_name": profile["name"],
        "ready_estimate": r["ready_estimate"],
        "hold_until": r["hold_until"],
        "arrived": bool(r["arrived_at"]),
        "created_at": r["created_at"],
        "medication": medications.to_dict(med),
        "pharmacy": {
            "id": ph["id"], "name": ph["name"], "address": ph["address"], "phone": ph["phone"],
            "lat": ph["lat"], "lng": ph["lng"],
            "pickup_counter": ph["pickup_counter"], "pickup_note": ph["pickup_note"],
        },
        "events": [{"text": e["text"], "at": e["created_at"]} for e in events],
    }


def _mask(cedula: str | None) -> str | None:
    """Cédula parcial: suficiente para confirmar identidad en el mostrador."""
    return f"•••{cedula[-4:]}" if cedula else None


def staff_view(conn: sqlite3.Connection, r: sqlite3.Row) -> dict:
    """Lo que ve el dispensador: el paciente, la fórmula y qué hay que hacer ahora."""
    med = conn.execute("SELECT * FROM medications WHERE id = ?", (r["medication_id"],)).fetchone()
    profile = conn.execute("SELECT name, relation, cedula, is_self FROM profiles WHERE id = ?", (r["profile_id"],)).fetchone()
    user = conn.execute("SELECT first_name, last_name, cedula, phone FROM users WHERE id = ?", (r["user_id"],)).fetchone()
    rx = (conn.execute("SELECT code, prescriber, specialty, instructions FROM prescriptions WHERE id = ?",
                       (r["prescription_id"],)).fetchone() if r["prescription_id"] else None)
    events = conn.execute(
        "SELECT text, actor, created_at FROM reservation_events WHERE reservation_id = ? ORDER BY created_at, id",
        (r["id"],),
    ).fetchall()
    patient_cedula = user["cedula"] if profile["is_self"] else profile["cedula"]
    return {
        "id": r["id"],
        "code": r["code"],
        "status": r["status"],
        "status_label": LABELS[r["status"]],
        "active": r["status"] not in CLOSED,
        "quantity": r["quantity"],
        "units_now": stock.current(conn, r["pharmacy_id"], r["medication_id"]),
        "patient": {
            "name": profile["name"],
            "cedula_hint": _mask(patient_cedula),
            # Si reserva un familiar, quien recoge puede ser otra persona.
            "account_holder": None if profile["is_self"] else f"{user['first_name']} {user['last_name']} ({profile['relation']})",
            "phone": user["phone"],
        },
        "medication": medications.to_dict(med),
        "prescription": dict(rx) if rx else None,
        "arrived_at": r["arrived_at"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "ready_estimate": r["ready_estimate"],
        "hold_until": r["hold_until"],
        "late": r["status"] in ("recibida", "en_preparacion") and parse(r["ready_estimate"]) < now(),
        "by_staff": bool(r["created_by_staff"]),
        "events": [{"text": e["text"], "actor": e["actor"], "at": e["created_at"]} for e in events],
    }
