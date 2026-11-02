"""Medicamentos y fórmulas médicas (recetas)."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from ..db import get_db, now, parse
from ..deps import current_user, own_profile
from ..services import images
from ..services.medications import to_dict as med_out
from ..services.text import normalize

router = APIRouter(prefix="/api", tags=["medicamentos"])


@router.get("/medications")
def search_medications(q: str = Query(min_length=2, max_length=60), user=Depends(current_user),
                       conn: sqlite3.Connection = Depends(get_db)):
    words = normalize(q).split()
    sql = "SELECT * FROM medications WHERE " + " AND ".join("search_text LIKE ?" for _ in words) + " ORDER BY name LIMIT 8"
    rows = conn.execute(sql, [f"%{w}%" for w in words]).fetchall()
    return [med_out(m) for m in rows]


@router.get("/medications/{medication_id}")
def get_medication(medication_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    m = conn.execute("SELECT * FROM medications WHERE id = ?", (medication_id,)).fetchone()
    if not m:
        raise HTTPException(404, "Medicamento no encontrado")
    return med_out(m)


# Sin sesión: es la foto de un producto, no un dato personal, y así la puede usar cualquier <img>.
@router.get("/medications/{medication_id}/image")
def medication_image(medication_id: int, conn: sqlite3.Connection = Depends(get_db)):
    m = conn.execute("SELECT * FROM medications WHERE id = ?", (medication_id,)).fetchone()
    if not m:
        raise HTTPException(404, "Medicamento no encontrado")
    # La dirección lleva la versión (?v=), así que se puede guardar en caché por mucho tiempo.
    cache = {"Cache-Control": "public, max-age=604800"}
    photo = images.file_for(m)
    if photo:
        return FileResponse(photo, media_type=images.ALLOWED[photo.suffix.lower()], headers=cache)
    return Response(images.placeholder_svg(m), media_type="image/svg+xml", headers=cache)


@router.get("/profiles/{profile_id}/prescriptions")
def prescriptions(profile_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    own_profile(conn, user, profile_id)
    rows = conn.execute(
        """SELECT p.*, m.name, m.strength, m.presentation, m.image FROM prescriptions p
           JOIN medications m ON m.id = p.medication_id
           WHERE p.profile_id = ? ORDER BY p.dispensed_at IS NOT NULL, p.expires_at""",
        (profile_id,),
    ).fetchall()
    today = now().date()
    out = []
    for r in rows:
        expires = parse(r["expires_at"]).date()
        if r["dispensed_at"]:
            state = "entregada"
        elif expires < today:
            state = "vencida"
        else:
            state = "vigente"
        out.append({
            "id": r["id"], "code": r["code"], "prescriber": r["prescriber"], "specialty": r["specialty"],
            "quantity": r["quantity"], "instructions": r["instructions"],
            "expires_at": r["expires_at"], "dispensed_at": r["dispensed_at"], "state": state,
            "days_left": (expires - today).days,
            "medication": med_out({**dict(r), "id": r["medication_id"]}),
        })
    return out
