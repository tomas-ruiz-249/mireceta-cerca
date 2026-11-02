"""Personal de la droguería: ingreso con usuario y contraseña, sesión por turno.

Usa el mismo hash lento (scrypt) y el mismo bloqueo por intentos fallidos que los pacientes.
"""

import hashlib
import secrets
import sqlite3
from datetime import timedelta

from ..config import settings
from ..db import iso, now, parse
from .auth import AuthError, hash_pin, verify_pin


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_password(password: str) -> None:
    if not password or len(password) < settings.staff_password_min:
        raise AuthError(f"La contraseña debe tener al menos {settings.staff_password_min} caracteres")


def create(conn: sqlite3.Connection, pharmacy_id: int, username: str, name: str, password: str) -> int:
    username = username.strip().lower()
    if not username or not name.strip():
        raise AuthError("Escriba el usuario y el nombre")
    check_password(password)
    if not conn.execute("SELECT 1 FROM pharmacies WHERE id = ?", (pharmacy_id,)).fetchone():
        raise AuthError("La droguería no existe")
    if conn.execute("SELECT 1 FROM staff WHERE username = ?", (username,)).fetchone():
        raise AuthError("Ese usuario ya existe")
    cur = conn.execute(
        "INSERT INTO staff (pharmacy_id, username, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (pharmacy_id, username, name.strip(), hash_pin(password), iso(now())),
    )
    return cur.lastrowid


def login(conn: sqlite3.Connection, username: str, password: str) -> int:
    row = conn.execute("SELECT * FROM staff WHERE username = ? AND active = 1",
                       ((username or "").strip().lower(),)).fetchone()
    generic = AuthError("El usuario o la contraseña no coinciden")
    if not row:
        raise generic
    if row["locked_until"] and parse(row["locked_until"]) > now():
        raise AuthError(f"Por seguridad, espere {settings.lockout_minutes} minutos e intente de nuevo")
    if not verify_pin(password or "", row["password_hash"]):
        failed = row["failed_logins"] + 1
        locked = iso(now() + timedelta(minutes=settings.lockout_minutes)) if failed >= settings.max_failed_logins else None
        conn.execute("UPDATE staff SET failed_logins = ?, locked_until = ? WHERE id = ?",
                     (0 if locked else failed, locked, row["id"]))
        if locked:
            raise AuthError(f"Demasiados intentos. Espere {settings.lockout_minutes} minutos")
        raise generic
    conn.execute("UPDATE staff SET failed_logins = 0, locked_until = NULL WHERE id = ?", (row["id"],))
    return row["id"]


def create_session(conn: sqlite3.Connection, staff_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO staff_sessions (token_hash, staff_id, expires_at) VALUES (?, ?, ?)",
                 (_token_hash(token), staff_id, iso(now() + timedelta(hours=settings.staff_session_hours))))
    return token


def for_token(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    row = conn.execute(
        """SELECT s.*, ss.expires_at FROM staff_sessions ss JOIN staff s ON s.id = ss.staff_id
           WHERE ss.token_hash = ? AND s.active = 1""",
        (_token_hash(token),),
    ).fetchone()
    if not row or parse(row["expires_at"]) < now():
        return None
    return row


def end_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM staff_sessions WHERE token_hash = ?", (_token_hash(token),))
