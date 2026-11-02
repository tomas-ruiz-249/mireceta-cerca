import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import connect, init_schema
from app.seed import DEMO_CEDULA, DEMO_PIN, seed


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    """La base de ejemplo se crea una sola vez (los hashes de PIN son lentos a propósito)."""
    path = tmp_path_factory.mktemp("plantilla") / "seed.db"
    conn = connect(path)
    init_schema(conn)
    seed(conn)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return path


@pytest.fixture
def db_path(tmp_path, template_db):
    path = tmp_path / "test.db"
    shutil.copy(template_db, path)
    object.__setattr__(settings, "db_path", path)  # Settings es inmutable a propósito; solo los tests lo cambian
    return path


@pytest.fixture
def conn(db_path):
    c = connect(db_path)
    yield c
    c.close()


@pytest.fixture
def client(db_path):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def logged(client):
    r = client.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": DEMO_PIN})
    assert r.status_code == 200, r.text
    return client
