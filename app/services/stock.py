"""Inventario por eventos: cada movimiento suma o resta; el stock es la suma.

Toda modificación del stock pasa por `add_movement`, así los avisos de
"llegó tu medicamento" se disparan siempre, venga el cambio de donde venga.
"""

import sqlite3

from ..config import settings
from ..db import iso, now
from . import live
from .notify import notify

KINDS = {
    "ingreso": "Ingreso de proveedor",
    "venta": "Venta",
    "reserva": "Apartado para una reserva",
    "liberacion": "Devolución de reserva no retirada",
    "ajuste": "Ajuste de inventario",
    "conteo": "Conteo de estantería",
}


class StockError(Exception):
    pass


def current(conn: sqlite3.Connection, pharmacy_id: int, medication_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(delta), 0) AS n FROM stock_movements WHERE pharmacy_id = ? AND medication_id = ?",
        (pharmacy_id, medication_id),
    ).fetchone()
    return row["n"]


def last_verified(conn: sqlite3.Connection, pharmacy_id: int, medication_id: int) -> str | None:
    row = conn.execute(
        "SELECT MAX(created_at) AS t FROM stock_movements WHERE pharmacy_id = ? AND medication_id = ?",
        (pharmacy_id, medication_id),
    ).fetchone()
    return row["t"]


def level(units: int) -> str:
    if units <= 0:
        return "none"
    if units <= settings.low_stock_threshold:
        return "low"
    return "ok"


def next_restock(conn: sqlite3.Connection, pharmacy_id: int, medication_id: int) -> str | None:
    row = conn.execute(
        """SELECT expected_date FROM restocks
           WHERE pharmacy_id = ? AND medication_id = ? AND received = 0 AND expected_date >= ?
           ORDER BY expected_date LIMIT 1""",
        (pharmacy_id, medication_id, now().date().isoformat()),
    ).fetchone()
    return row["expected_date"] if row else None


def movements(conn: sqlite3.Connection, pharmacy_id: int, medication_id: int, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT id, delta, kind, note, scanned, created_at FROM stock_movements
           WHERE pharmacy_id = ? AND medication_id = ? ORDER BY created_at DESC, id DESC""",
        (pharmacy_id, medication_id),
    ).fetchall()
    # Saldo después de cada movimiento, calculado desde el total actual hacia atrás.
    balance = sum(r["delta"] for r in rows)
    out = []
    for r in rows[:limit]:
        label = KINDS.get(r["kind"], r["kind"])
        if r["scanned"]:
            label += " · verificado por escaneo"
        out.append({"at": r["created_at"], "label": label, "note": r["note"], "delta": r["delta"], "balance": balance})
        balance -= r["delta"]
    return out


def add_movement(
    conn: sqlite3.Connection,
    pharmacy_id: int,
    medication_id: int,
    delta: int,
    kind: str,
    note: str | None = None,
    scanned: bool = False,
    reservation_id: int | None = None,
) -> int:
    """Registra un movimiento. Debe llamarse dentro de una transacción."""
    if kind not in KINDS:
        raise StockError(f"Tipo de movimiento desconocido: {kind}")
    before = current(conn, pharmacy_id, medication_id)
    after = before + delta
    if after < 0:
        raise StockError("No hay unidades suficientes")
    conn.execute(
        """INSERT INTO stock_movements
           (pharmacy_id, medication_id, delta, kind, note, scanned, reservation_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (pharmacy_id, medication_id, delta, kind, note, int(scanned), reservation_id, iso(now())),
    )
    live.emit(conn, live.pharmacy(pharmacy_id), "stock", medication_id)
    if kind == "ingreso":
        conn.execute(
            """UPDATE restocks SET received = 1
               WHERE pharmacy_id = ? AND medication_id = ? AND received = 0 AND expected_date <= ?""",
            (pharmacy_id, medication_id, now().date().isoformat()),
        )
    if before <= 0 < after:
        _fulfill_alerts(conn, pharmacy_id, medication_id)
    return after


def _fulfill_alerts(conn: sqlite3.Connection, pharmacy_id: int, medication_id: int) -> None:
    alerts = conn.execute(
        "SELECT id, user_id FROM stock_alerts WHERE pharmacy_id = ? AND medication_id = ? AND fulfilled_at IS NULL",
        (pharmacy_id, medication_id),
    ).fetchall()
    if not alerts:
        return
    ph = conn.execute("SELECT name FROM pharmacies WHERE id = ?", (pharmacy_id,)).fetchone()
    med = conn.execute("SELECT name, strength FROM medications WHERE id = ?", (medication_id,)).fetchone()
    for alert in alerts:
        notify(
            conn,
            alert["user_id"],
            "Llegó su medicamento",
            f"{med['name']} {med['strength']} ya está disponible en {ph['name']}.",
            f"#/drogueria/{pharmacy_id}/{medication_id}",
        )
        conn.execute("UPDATE stock_alerts SET fulfilled_at = ? WHERE id = ?", (iso(now()), alert["id"]))
