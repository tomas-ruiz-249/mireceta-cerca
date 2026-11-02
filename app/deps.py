"""Dependencias compartidas por los routers."""

import sqlite3

from fastapi import Cookie, Depends, HTTPException

from .db import get_db
from .services import auth, staff

SESSION_COOKIE = "mireceta_sesion"
STAFF_COOKIE = "mireceta_personal"   # sesión del dispensador, independiente de la del paciente


def current_user(
    conn: sqlite3.Connection = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> sqlite3.Row:
    user = auth.user_for_token(conn, token)
    if not user:
        raise HTTPException(401, "Debe ingresar de nuevo")
    return user


def own_profile(conn: sqlite3.Connection, user: sqlite3.Row, profile_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM profiles WHERE id = ? AND user_id = ?", (profile_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "No encontramos a esa persona")
    return row


def current_staff(
    conn: sqlite3.Connection = Depends(get_db),
    token: str | None = Cookie(default=None, alias=STAFF_COOKIE),
) -> sqlite3.Row:
    row = staff.for_token(conn, token)
    if not row:
        raise HTTPException(401, "Su turno terminó. Ingrese de nuevo")
    return row
