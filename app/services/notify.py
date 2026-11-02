"""Avisos al usuario.

Todo aviso se guarda en la tabla `notifications` (la app lo muestra).
Además se envía por cada canal registrado en CHANNELS. Para agregar SMS o
WhatsApp, escribe una función con la misma firma y agrégala a la lista.
"""

import logging
import sqlite3
from collections.abc import Callable

from ..db import iso, now
from . import live

log = logging.getLogger("mireceta.notify")

Channel = Callable[[sqlite3.Row, str, str], None]


def log_channel(user: sqlite3.Row, title: str, body: str) -> None:
    log.info("Aviso para %s (%s): %s — %s", user["first_name"], user["phone"] or "sin celular", title, body)


CHANNELS: list[Channel] = [log_channel]


def notify(conn: sqlite3.Connection, user_id: int, title: str, body: str, link: str | None = None) -> None:
    conn.execute(
        "INSERT INTO notifications (user_id, title, body, link, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, title, body, link, iso(now())),
    )
    live.emit(conn, live.user(user_id), "notification")
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    for channel in CHANNELS:
        try:
            channel(user, title, body)
        except Exception:  # un canal caído no debe impedir la reserva
            log.exception("Falló el canal de aviso %s", channel.__name__)
