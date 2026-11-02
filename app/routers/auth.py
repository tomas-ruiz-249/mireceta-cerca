import sqlite3

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from ..config import settings
from ..db import get_db, transaction
from ..deps import SESSION_COOKIE, current_user
from ..schemas import ChangePinIn, LoginIn, RegisterIn
from ..services import auth

router = APIRouter(prefix="/api/auth", tags=["ingreso"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=settings.session_days * 86400,
        httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
    )


def _me(user: sqlite3.Row) -> dict:
    return {"id": user["id"], "first_name": user["first_name"], "last_name": user["last_name"],
            "cedula": user["cedula"], "phone": user["phone"]}


@router.post("/login")
def login(body: LoginIn, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    try:
        uid = auth.login(conn, body.cedula, body.pin)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    _set_cookie(response, auth.create_session(conn, uid))
    return _me(conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())


@router.post("/register")
def register(body: RegisterIn, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    try:
        with transaction(conn):
            uid = auth.register(conn, body.cedula, body.first_name, body.last_name, body.pin, body.phone,
                                body.activation_code)
    except auth.ActivationNeeded as e:
        # 428: el navegador muestra el campo "código de la droguería".
        raise HTTPException(428, str(e))
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    _set_cookie(response, auth.create_session(conn, uid))
    return _me(conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())


@router.post("/logout")
def logout(response: Response, conn: sqlite3.Connection = Depends(get_db),
           token: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    auth.end_session(conn, token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(current_user)):
    return _me(user)


@router.post("/pin")
def change_pin(body: ChangePinIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    try:
        auth.change_pin(conn, user["id"], body.pin)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}
