import sqlite3
import struct
import zlib

import pytest

from app.db import connect, init_schema
from app.services import images


def _png(path):
    """PNG de 1×1 píxel, sin dependencias."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw += chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"")
    path.write_bytes(raw)
    return path


def test_every_medication_has_an_image_url(logged):
    med = logged.get("/api/medications", params={"q": "losartan"}).json()[0]
    assert med["image_url"].startswith(f"/api/medications/{med['id']}/image?v=")
    assert med["has_photo"] is False


def test_drawn_box_when_there_is_no_photo(client):
    r = client.get("/api/medications/1/image")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "Losartán" in r.text and "50 mg" in r.text


def test_uploaded_photo_replaces_drawing(logged, conn, tmp_path):
    before = logged.get("/api/medications/1").json()["image_url"]
    images.save(conn, 1, _png(tmp_path / "caja.png"))
    med = logged.get("/api/medications/1").json()
    assert med["has_photo"] is True and med["image_url"] != before
    r = logged.get(med["image_url"])
    assert r.headers["content-type"] == "image/png"

    # La reserva y las fórmulas muestran la misma foto
    rx = logged.get("/api/profiles/1/prescriptions").json()
    assert next(x for x in rx if x["medication"]["id"] == 1)["medication"]["image_url"] == med["image_url"]

    images.remove(conn, 1)
    assert logged.get("/api/medications/1").json()["has_photo"] is False
    assert not list(images.media_dir().glob("med-1-*"))  # el archivo viejo se borra


def test_rejects_non_images(conn, tmp_path):
    bad = tmp_path / "virus.exe"
    bad.write_bytes(b"x")
    with pytest.raises(images.ImageError):
        images.save(conn, 1, bad)


def test_old_database_gets_image_column(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE medications (id INTEGER PRIMARY KEY, name TEXT NOT NULL, strength TEXT NOT NULL, "
                "presentation TEXT NOT NULL, search_text TEXT NOT NULL)")
    old.commit()
    old.close()
    conn = connect(path)
    init_schema(conn)
    assert "image" in {r["name"] for r in conn.execute("PRAGMA table_info(medications)")}
