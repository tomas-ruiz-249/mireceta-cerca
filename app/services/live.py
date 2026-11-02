"""Eventos en vivo: la app del dispensador y la del paciente se enteran al instante.

Cómo funciona:
  1. Cada cambio importante llama a `emit(conn, canal, tipo)`, que guarda una fila en
     `live_events` dentro de la misma transacción que el cambio.
  2. Al confirmar la transacción se "despierta" a las conexiones abiertas (`wake`).
  3. `stream()` envía al navegador los eventos nuevos de sus canales (Server-Sent Events).
     El navegador vuelve a pedir los datos y redibuja.

Como el evento vive en la base de datos, también llegan los cambios hechos desde la
terminal (`app.cli`) o desde otro proceso del servidor: en ese caso se detectan en
menos de `settings.live_poll_seconds`.
"""

import asyncio
import json
import sqlite3
import time
from collections.abc import AsyncIterator, Callable
from datetime import timedelta

from ..config import settings
from ..db import after_commit, connect, iso, now

# Una señal por bucle de eventos (normalmente hay uno solo: el del servidor).
_signals: dict[asyncio.AbstractEventLoop, asyncio.Event] = {}


def pharmacy(pharmacy_id: int) -> str:
    return f"pharmacy:{pharmacy_id}"


def user(user_id: int) -> str:
    return f"user:{user_id}"


def emit(conn: sqlite3.Connection, channel: str, kind: str, ref_id: int | None = None) -> None:
    conn.execute(
        "INSERT INTO live_events (channel, kind, ref_id, created_at) VALUES (?, ?, ?, ?)",
        (channel, kind, ref_id, iso(now())),
    )
    if not conn.in_transaction:  # sin transacción abierta ya quedó guardado
        wake()


def _fire(loop: asyncio.AbstractEventLoop) -> None:
    old = _signals.get(loop)
    _signals[loop] = asyncio.Event()
    if old is not None:
        old.set()


def wake() -> None:
    """Despierta a quien escucha. Se puede llamar desde cualquier hilo; sin servidor no hace nada."""
    for loop in list(_signals):
        try:
            loop.call_soon_threadsafe(_fire, loop)
        except RuntimeError:  # bucle cerrado
            _signals.pop(loop, None)


after_commit.append(wake)


async def _wait(timeout: float) -> None:
    loop = asyncio.get_running_loop()
    signal = _signals.setdefault(loop, asyncio.Event())
    try:
        await asyncio.wait_for(signal.wait(), timeout)
    except TimeoutError:
        pass


def latest_id(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COALESCE(MAX(id), 0) FROM live_events").fetchone()[0]


def prune(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM live_events WHERE created_at < ?", (iso(now() - timedelta(days=1)),))


def _sse(event_id: int | None, kind: str, data: dict) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {kind}\ndata: {json.dumps(data)}\n\n"


async def stream(
    channels: list[str],
    last_event_id: str | None,
    is_disconnected: Callable,
    housekeeping: Callable[[sqlite3.Connection], None] | None = None,
) -> AsyncIterator[str]:
    """Generador SSE. Termina solo tras `settings.live_stream_seconds`; el navegador reconecta."""
    conn = connect()
    try:
        newest = latest_id(conn)
        try:
            last = int(last_event_id) if last_event_id else newest
        except ValueError:
            last = newest
        # Tras una desconexión larga no tiene sentido repetir cientos de eventos viejos:
        # el navegador pide los datos frescos de todas formas.
        if last > newest or newest - last > 200:
            last = newest
        marks = ",".join("?" * len(channels))
        # 'retry': el navegador espera 3 s antes de reconectar si se cae la conexión.
        yield "retry: 3000\n" + _sse(last, "hello", {"ok": True})
        deadline = time.monotonic() + settings.live_stream_seconds
        last_ping = last_chores = time.monotonic()
        while time.monotonic() < deadline:
            if await is_disconnected():
                break
            if housekeeping and time.monotonic() - last_chores > 30:
                housekeeping(conn)
                last_chores = time.monotonic()
            rows = conn.execute(
                f"SELECT id, kind, ref_id FROM live_events WHERE id > ? AND channel IN ({marks}) ORDER BY id",
                (last, *channels),
            ).fetchall()
            for r in rows:
                last = r["id"]
                yield _sse(r["id"], r["kind"], {"kind": r["kind"], "ref": r["ref_id"]})
            if not rows and time.monotonic() - last_ping > 15:
                yield ": sigo aquí\n\n"  # mantiene viva la conexión a través de proxies
                last_ping = time.monotonic()
            await _wait(settings.live_poll_seconds)
    finally:
        conn.close()


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
