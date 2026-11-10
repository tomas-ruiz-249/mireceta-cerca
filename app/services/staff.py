"""Cuentas del personal: dispensadores (droguería) y médicos. Usuario y contraseña, sesión por turno.

Usa el mismo hash lento (scrypt) y el mismo bloqueo por intentos fallidos que los pacientes.
`kind` elige el tipo de cuenta: "staff" (dispensador) o "doctor" (médico).
"""

import hashlib
import secrets
import sqlite3
from datetime import timedelta

from ..config import settings
from ..db import iso, now, parse
from .auth import AuthError, hash_pin, verify_pin


# kind -> (tabla de cuentas, tabla de sesiones, columna que las une). Nombres fijos, nunca del usuario.
_TABLES = {"staff": ("staff", "staff_sessions", "staff_id"), "doctor": ("doctors", "doctor_sessions", "doctor_id")}


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


def login(conn: sqlite3.Connection, username: str, password: str, kind: str = "staff") -> int:
    table = _TABLES[kind][0]
    row = conn.execute(f"SELECT * FROM {table} WHERE username = ? AND active = 1",
                       ((username or "").strip().lower(),)).fetchone()
    generic = AuthError("El usuario o la contraseña no coinciden")
    if not row:
        raise generic
    if row["locked_until"] and parse(row["locked_until"]) > now():
        raise AuthError(f"Por seguridad, espere {settings.lockout_minutes} minutos e intente de nuevo")
    if not verify_pin(password or "", row["password_hash"]):
        failed = row["failed_logins"] + 1
        locked = iso(now() + timedelta(minutes=settings.lockout_minutes)) if failed >= settings.max_failed_logins else None
        conn.execute(f"UPDATE {table} SET failed_logins = ?, locked_until = ? WHERE id = ?",
                     (0 if locked else failed, locked, row["id"]))
        if locked:
            raise AuthError(f"Demasiados intentos. Espere {settings.lockout_minutes} minutos")
        raise generic
    conn.execute(f"UPDATE {table} SET failed_logins = 0, locked_until = NULL WHERE id = ?", (row["id"],))
    return row["id"]


def create_session(conn: sqlite3.Connection, account_id: int, kind: str = "staff") -> str:
    _, sessions, col = _TABLES[kind]
    token = secrets.token_urlsafe(32)
    conn.execute(f"INSERT INTO {sessions} (token_hash, {col}, expires_at) VALUES (?, ?, ?)",
                 (_token_hash(token), account_id, iso(now() + timedelta(hours=settings.staff_session_hours))))
    return token


def for_token(conn: sqlite3.Connection, token: str | None, kind: str = "staff") -> sqlite3.Row | None:
    if not token:
        return None
    table, sessions, col = _TABLES[kind]
    row = conn.execute(
        f"""SELECT a.*, ss.expires_at FROM {sessions} ss JOIN {table} a ON a.id = ss.{col}
            WHERE ss.token_hash = ? AND a.active = 1""",
        (_token_hash(token),),
    ).fetchone()
    if not row or parse(row["expires_at"]) < now():
        return None
    return row


def end_session(conn: sqlite3.Connection, token: str | None, kind: str = "staff") -> None:
    if token:
        conn.execute(f"DELETE FROM {_TABLES[kind][1]} WHERE token_hash = ?", (_token_hash(token),))


def create_doctor(conn: sqlite3.Connection, username: str, name: str, specialty: str, password: str,
                  license: str | None = None) -> int:
    username = username.strip().lower()
    if not username or not name.strip() or not specialty.strip():
        raise AuthError("Escriba el usuario, el nombre y la especialidad")
    check_password(password)
    if conn.execute("SELECT 1 FROM doctors WHERE username = ?", (username,)).fetchone():
        raise AuthError("Ese usuario ya existe")
    return conn.execute(
        "INSERT INTO doctors (username, name, specialty, license, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (username, name.strip(), specialty.strip(), (license or "").strip() or None, hash_pin(password), iso(now())),
    ).lastrowid
