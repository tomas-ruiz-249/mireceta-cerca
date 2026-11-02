"""Perfil familiar: consultar y reservar por otras personas del hogar."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..deps import current_user, own_profile
from ..schemas import ProfileIn
from ..services.auth import AuthError, clean_cedula

router = APIRouter(prefix="/api/profiles", tags=["familia"])


def _out(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "name": r["name"], "relation": r["relation"], "is_self": bool(r["is_self"])}


@router.get("")
def list_profiles(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY is_self DESC, id", (user["id"],)).fetchall()
    return [_out(r) for r in rows]


@router.post("")
def add_profile(body: ProfileIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    try:
        cedula = clean_cedula(body.cedula) if body.cedula else None
    except AuthError as e:
        raise HTTPException(400, str(e))
    cur = conn.execute(
        "INSERT INTO profiles (user_id, name, relation, cedula) VALUES (?, ?, ?, ?)",
        (user["id"], body.name.strip(), body.relation.strip(), cedula),
    )
    return _out(conn.execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.delete("/{profile_id}")
def remove_profile(profile_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    p = own_profile(conn, user, profile_id)
    if p["is_self"]:
        raise HTTPException(400, "No puede quitar su propio perfil")
    in_use = conn.execute(
        "SELECT 1 FROM prescriptions WHERE profile_id = ? UNION SELECT 1 FROM reservations WHERE profile_id = ?",
        (profile_id, profile_id),
    ).fetchone()
    if in_use:
        raise HTTPException(400, "Esta persona tiene fórmulas o reservas, no se puede quitar")
    conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    return {"ok": True}
