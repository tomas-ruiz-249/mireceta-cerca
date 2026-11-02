"""Acceso a SQLite. Una conexión por petición; las fechas se guardan en ISO 8601 con zona horaria."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import settings

SCHEMA = Path(__file__).with_name("schema.sql")


def now() -> datetime:
    return datetime.now(settings.timezone).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # autocommit; usamos transaction() explícito. FastAPI puede abrir la conexión en un hilo
    # y usarla en otro, pero cada conexión pertenece a una sola petición.
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# Columnas agregadas después de la primera versión: (tabla, columna, definición).
# Las bases creadas antes las reciben al arrancar, sin perder datos.
MIGRATIONS = [
    ("medications", "image", "TEXT"),
    ("reservation_events", "actor", "TEXT"),       # quién de la droguería hizo el cambio
    ("reservations", "created_by_staff", "INTEGER"),  # reserva hecha en el mostrador o por teléfono
    ("users", "activation_hash", "TEXT"),             # código para reclamar una cuenta abierta en la droguería
]

# Funciones que se llaman justo después de cada COMMIT (las usa services/live.py
# para despertar a quien está escuchando eventos en vivo).
after_commit: list = []


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    for table, column, definition in MIGRATIONS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def transaction(conn: sqlite3.Connection):
    """BEGIN IMMEDIATE evita que dos reservas tomen la misma última caja."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
        for fn in after_commit:
            fn()


def get_db():
    """Dependencia de FastAPI."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
