"""Ingreso con cédula + PIN de 4 dígitos.

El PIN es corto, así que la protección real es el bloqueo tras varios
intentos fallidos y un hash lento (scrypt) en la base de datos.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import timedelta

from ..config import settings
from ..db import iso, now, parse

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}
CEDULA_RE = re.compile(r"^\d{6,10}$")  # cédula de ciudadanía colombiana


class AuthError(Exception):
    pass


class ActivationNeeded(AuthError):
    """La cuenta la abrió la droguería: para reclamarla se pide el código que entregó el mostrador."""


def clean_cedula(value: str) -> str:
    digits = re.sub(r"[\s.\-]", "", value or "")
    if not CEDULA_RE.match(digits):
        raise AuthError("La cédula debe tener entre 6 y 10 números")
    return digits


def check_pin_format(pin: str) -> None:
    if not (pin and pin.isdigit() and len(pin) == settings.pin_length):
        raise AuthError(f"El PIN debe tener {settings.pin_length} números")


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    if not stored:  # cuenta creada en la droguería, todavía sin PIN
        return False
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


def register(conn: sqlite3.Connection, cedula: str, first_name: str, last_name: str, pin: str, phone: str | None,
             activation_code: str | None = None) -> int:
    cedula = clean_cedula(cedula)
    check_pin_format(pin)
    if not first_name.strip() or not last_name.strip():
        raise AuthError("Escriba su nombre y apellido")
    existing = conn.execute("SELECT * FROM users WHERE cedula = ?", (cedula,)).fetchone()
    if existing and existing["pin_hash"]:
        raise AuthError("Ya existe una cuenta con esa cédula")
    if existing:
        # La droguería le abrió la cuenta (paciente sin celular inteligente). Ahora la
        # persona, o un familiar, la reclama con el código del mostrador y elige su PIN;
        # sus reservas siguen ahí. Sin el código, nadie puede apoderarse de la cuenta
        # solo con saber la cédula.
        code = (activation_code or "").strip()
        if not code:
            raise ActivationNeeded("La droguería ya le abrió una cuenta. Escriba el código de 6 números que le dieron")
        if not (existing["activation_hash"] and verify_pin(code, existing["activation_hash"])):
            raise ActivationNeeded("El código de la droguería no coincide. Pídalo de nuevo en el mostrador")
        conn.execute(
            "UPDATE users SET first_name = ?, last_name = ?, phone = COALESCE(?, phone), pin_hash = ?, activation_hash = NULL WHERE id = ?",
            (first_name.strip(), last_name.strip(), (phone or "").strip() or None, hash_pin(pin), existing["id"]),
        )
        return existing["id"]
    cur = conn.execute(
        "INSERT INTO users (cedula, first_name, last_name, phone, pin_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (cedula, first_name.strip(), last_name.strip(), (phone or "").strip() or None, hash_pin(pin), iso(now())),
    )
    uid = cur.lastrowid
    conn.execute(
        "INSERT INTO profiles (user_id, name, relation, cedula, is_self) VALUES (?, ?, 'yo', ?, 1)",
        (uid, f"{first_name.strip()} {last_name.strip()}", cedula),
    )
    return uid


def register_at_pharmacy(conn: sqlite3.Connection, cedula: str, first_name: str, last_name: str,
                         phone: str | None) -> tuple[int, str]:
    """El personal registra a un paciente que no usa la app. Queda sin PIN: no se puede
    ingresar hasta que la persona lo elija con «Crear mi cuenta» y el código de activación
    que se devuelve aquí (el mostrador se lo entrega anotado)."""
    cedula = clean_cedula(cedula)
    if not first_name.strip() or not last_name.strip():
        raise AuthError("Escriba el nombre y el apellido del paciente")
    if conn.execute("SELECT 1 FROM users WHERE cedula = ?", (cedula,)).fetchone():
        raise AuthError("Ya existe un paciente con esa cédula")
    code = f"{secrets.randbelow(10**6):06d}"
    uid = conn.execute(
        "INSERT INTO users (cedula, first_name, last_name, phone, pin_hash, activation_hash, created_at) "
        "VALUES (?, ?, ?, ?, '', ?, ?)",
        (cedula, first_name.strip(), last_name.strip(), (phone or "").strip() or None, hash_pin(code), iso(now())),
    ).lastrowid
    conn.execute(
        "INSERT INTO profiles (user_id, name, relation, cedula, is_self) VALUES (?, ?, 'yo', ?, 1)",
        (uid, f"{first_name.strip()} {last_name.strip()}", cedula),
    )
    return uid, code


def login(conn: sqlite3.Connection, cedula: str, pin: str) -> int:
    cedula = clean_cedula(cedula)
    user = conn.execute("SELECT * FROM users WHERE cedula = ?", (cedula,)).fetchone()
    generic = AuthError("La cédula o el PIN no coinciden")
    if not user:
        raise generic
    if not user["pin_hash"]:
        raise AuthError("Su cuenta se abrió en la droguería. Toque «Crear mi cuenta» para elegir su PIN")
    if user["locked_until"] and parse(user["locked_until"]) > now():
        raise AuthError(f"Por seguridad, espere {settings.lockout_minutes} minutos e intente de nuevo")
    if not verify_pin(pin or "", user["pin_hash"]):
        failed = user["failed_logins"] + 1
        locked = iso(now() + timedelta(minutes=settings.lockout_minutes)) if failed >= settings.max_failed_logins else None
        conn.execute(
            "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
            (0 if locked else failed, locked, user["id"]),
        )
        if locked:
            raise AuthError(f"Demasiados intentos. Espere {settings.lockout_minutes} minutos e intente de nuevo")
        raise generic
    conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
    return user["id"]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, iso(now() + timedelta(days=settings.session_days))),
    )
    return token


def user_for_token(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (_token_hash(token),),
    ).fetchone()
    if not row or parse(row["expires_at"]) < now():
        return None
    return row


def end_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def change_pin(conn: sqlite3.Connection, user_id: int, new_pin: str) -> None:
    check_pin_format(new_pin)
    conn.execute("UPDATE users SET pin_hash = ?, activation_hash = NULL WHERE id = ?", (hash_pin(new_pin), user_id))
