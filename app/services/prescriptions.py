"""Fórmulas médicas. Solo un médico registrado las emite (app del médico, /medico).

    vigente -> reservada (hay una reserva en curso) -> entregada
        \\-> vencida (pasó la fecha) / anulada (el médico la anuló antes de entregarla)

Al emitir o anular, el paciente recibe el aviso al instante y la fórmula aparece
(o desaparece) en su app y en la de la droguería. Cuando la droguería la reserva o
la entrega, el médico lo ve en vivo en «Mis fórmulas».
"""

import sqlite3
from datetime import timedelta

from ..db import iso, now, parse, transaction
from . import live, medications
from .notify import notify

ACTIVE_RESERVATION = ("recibida", "en_preparacion", "lista")
LABELS = {
    "vigente": "Vigente",
    "reservada": "Reservada en droguería",
    "entregada": "Entregada",
    "vencida": "Vencida",
    "anulada": "Anulada",
}
MAX_ITEMS = 8
MAX_VALID_DAYS = 180


class PrescriptionError(Exception):
    pass


def _new_code(conn: sqlite3.Connection) -> str:
    year = now().year
    n = conn.execute("SELECT COALESCE(MAX(id), 0) FROM prescriptions").fetchone()[0] + 5001
    while conn.execute("SELECT 1 FROM prescriptions WHERE code = ?", (code := f"FM-{year}-{n:06d}",)).fetchone():
        n += 1
    return code


def state(conn: sqlite3.Connection, rx: sqlite3.Row) -> tuple[str, sqlite3.Row | None]:
    """Estado actual y, si existe, la reserva en curso."""
    if rx["cancelled_at"]:
        return "anulada", None
    if rx["dispensed_at"]:
        return "entregada", None
    res = conn.execute(
        f"""SELECT r.*, ph.name AS pharmacy_name FROM reservations r JOIN pharmacies ph ON ph.id = r.pharmacy_id
            WHERE r.prescription_id = ? AND r.status IN ({",".join("?" * len(ACTIVE_RESERVATION))})
            ORDER BY r.id DESC LIMIT 1""",
        (rx["id"], *ACTIVE_RESERVATION),
    ).fetchone()
    if res:
        return "reservada", res
    if parse(rx["expires_at"]) < now():
        return "vencida", None
    return "vigente", None


def usable(rx: sqlite3.Row | None) -> str | None:
    """Motivo por el que no se puede reservar con esta fórmula, o None si se puede."""
    if not rx:
        return "La fórmula no existe"
    if rx["cancelled_at"]:
        return "El médico anuló esta fórmula"
    if rx["dispensed_at"]:
        return "Esta fórmula ya fue entregada"
    if parse(rx["expires_at"]) < now():
        return "Esta fórmula está vencida. Pida una nueva a su médico"
    return None


def issue(conn: sqlite3.Connection, doctor: sqlite3.Row, profile_id: int, items: list[dict],
          valid_days: int = 30) -> list[int]:
    """Emite una fórmula con uno o varios medicamentos. Cada medicamento lleva su propio código."""
    if not items:
        raise PrescriptionError("Agregue al menos un medicamento")
    if len(items) > MAX_ITEMS:
        raise PrescriptionError(f"Máximo {MAX_ITEMS} medicamentos por fórmula")
    if not 1 <= valid_days <= MAX_VALID_DAYS:
        raise PrescriptionError(f"La vigencia debe ser de 1 a {MAX_VALID_DAYS} días")
    seen = set()
    for it in items:
        if it["medication_id"] in seen:
            raise PrescriptionError("Hay un medicamento repetido en la fórmula")
        seen.add(it["medication_id"])
    profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not profile:
        raise PrescriptionError("Paciente no encontrado")

    t = now()
    ids, names = [], []
    with transaction(conn):
        for it in items:
            med = conn.execute("SELECT * FROM medications WHERE id = ?", (it["medication_id"],)).fetchone()
            if not med:
                raise PrescriptionError("Medicamento no encontrado")
            ids.append(conn.execute(
                """INSERT INTO prescriptions (profile_id, medication_id, code, prescriber, specialty, quantity,
                   instructions, issued_at, expires_at, doctor_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (profile_id, med["id"], _new_code(conn), doctor["name"], doctor["specialty"], it["quantity"],
                 (it.get("instructions") or "").strip() or None, iso(t), iso(t + timedelta(days=valid_days)),
                 doctor["id"]),
            ).lastrowid)
            names.append(f"{med['name']} {med['strength']}")
        whom = "" if profile["is_self"] else f" para {profile['name']}"
        notify(conn, profile["user_id"], "Nueva fórmula médica",
               f"{doctor['name']} le formuló{whom}: {', '.join(names)}. Ya puede buscar dónde la tienen y reservarla.",
               "#/")
        live.emit(conn, live.user(profile["user_id"]), "prescription", ids[0])
        live.emit(conn, live.doctor(doctor["id"]), "prescription", ids[0])
    return ids


def cancel(conn: sqlite3.Connection, prescription_id: int, doctor_id: int, reason: str) -> None:
    reason = (reason or "").strip()
    if not reason:
        raise PrescriptionError("Escriba el motivo")
    with transaction(conn):
        rx = conn.execute("SELECT * FROM prescriptions WHERE id = ? AND doctor_id = ?",
                          (prescription_id, doctor_id)).fetchone()
        if not rx:
            raise PrescriptionError("La fórmula no existe o la emitió otro médico")
        st, res = state(conn, rx)
        if st == "entregada":
            raise PrescriptionError("Ya fue entregada: no se puede anular")
        if st == "anulada":
            raise PrescriptionError("Ya estaba anulada")
        if res:
            raise PrescriptionError(f"Ya está reservada en {res['pharmacy_name']} (código {res['code']}). "
                                    "Pida a la droguería que cancele la reserva y luego anúlela")
        conn.execute("UPDATE prescriptions SET cancelled_at = ?, cancel_reason = ? WHERE id = ?",
                     (iso(now()), reason, rx["id"]))
        profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (rx["profile_id"],)).fetchone()
        med = conn.execute("SELECT name, strength FROM medications WHERE id = ?", (rx["medication_id"],)).fetchone()
        notify(conn, profile["user_id"], "Su médico anuló una fórmula",
               f"{rx['prescriber']} anuló la fórmula {rx['code']} ({med['name']} {med['strength']}). Motivo: {reason}",
               "#/")
        live.emit(conn, live.user(profile["user_id"]), "prescription", rx["id"])
        live.emit(conn, live.doctor(doctor_id), "prescription", rx["id"])


def broadcast_to_doctor(conn: sqlite3.Connection, prescription_id: int | None) -> None:
    """La droguería reservó o entregó: el médico que la emitió lo ve en vivo."""
    if not prescription_id:
        return
    row = conn.execute("SELECT doctor_id FROM prescriptions WHERE id = ?", (prescription_id,)).fetchone()
    if row and row["doctor_id"]:
        live.emit(conn, live.doctor(row["doctor_id"]), "prescription", prescription_id)


def view(conn: sqlite3.Connection, rx: sqlite3.Row) -> dict:
    """Lo que ve el médico de una fórmula."""
    st, res = state(conn, rx)
    med = conn.execute("SELECT * FROM medications WHERE id = ?", (rx["medication_id"],)).fetchone()
    profile = conn.execute("SELECT name FROM profiles WHERE id = ?", (rx["profile_id"],)).fetchone()
    return {
        "id": rx["id"], "code": rx["code"], "state": st, "state_label": LABELS[st],
        "patient": profile["name"],
        "prescriber": rx["prescriber"], "specialty": rx["specialty"],
        "quantity": rx["quantity"], "instructions": rx["instructions"],
        "issued_at": rx["issued_at"], "expires_at": rx["expires_at"],
        "dispensed_at": rx["dispensed_at"], "cancelled_at": rx["cancelled_at"], "cancel_reason": rx["cancel_reason"],
        "reservation": {"code": res["code"], "pharmacy": res["pharmacy_name"], "status": res["status"]} if res else None,
        "doctor_id": rx["doctor_id"],
        "medication": medications.to_dict(med),
    }
