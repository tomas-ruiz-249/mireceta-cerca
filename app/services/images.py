"""Fotos de los medicamentos.

Si un medicamento tiene foto cargada (python -m app.cli medication-image), se usa esa.
Si no, se dibuja una caja con el nombre y la concentración, para que la persona
siempre vea algo reconocible.
"""

import hashlib
import shutil
import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

from ..config import settings

ALLOWED = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_BYTES = 5 * 1024 * 1024


class ImageError(Exception):
    pass


def media_dir() -> Path:
    d = settings.db_path.parent / "media"
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_for(med: sqlite3.Row) -> Path | None:
    if not med["image"]:
        return None
    path = media_dir() / med["image"]
    return path if path.exists() else None


def url_for(med: sqlite3.Row) -> str:
    # La versión en la dirección hace que el navegador pida la foto nueva cuando se cambia.
    version = med["image"] or hashlib.sha1(f"{med['name']}{med['strength']}{med['presentation']}".encode()).hexdigest()[:8]
    return f"/api/medications/{med['id']}/image?v={version}"


def save(conn: sqlite3.Connection, medication_id: int, source: Path) -> str:
    source = Path(source)
    ext = source.suffix.lower()
    if ext not in ALLOWED:
        raise ImageError("La foto debe ser JPG, PNG o WEBP")
    if not source.is_file():
        raise ImageError(f"No existe el archivo {source}")
    if source.stat().st_size > MAX_BYTES:
        raise ImageError("La foto pesa más de 5 MB")
    if not conn.execute("SELECT 1 FROM medications WHERE id = ?", (medication_id,)).fetchone():
        raise ImageError("Medicamento no encontrado")
    digest = hashlib.sha1(source.read_bytes()).hexdigest()[:10]
    name = f"med-{medication_id}-{digest}{ext}"
    shutil.copyfile(source, media_dir() / name)
    _replace(conn, medication_id, name)
    return name


def remove(conn: sqlite3.Connection, medication_id: int) -> None:
    _replace(conn, medication_id, None)


def _replace(conn: sqlite3.Connection, medication_id: int, name: str | None) -> None:
    old = conn.execute("SELECT image FROM medications WHERE id = ?", (medication_id,)).fetchone()
    conn.execute("UPDATE medications SET image = ? WHERE id = ?", (name, medication_id))
    if old and old["image"] and old["image"] != name:
        (media_dir() / old["image"]).unlink(missing_ok=True)


def _wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    return lines[:3]


def _hue(text: str) -> int:
    """Un color estable por medicamento, para distinguir cajas parecidas."""
    return int(hashlib.sha1(text.encode()).hexdigest()[:4], 16) % 360


def _form_icon(presentation: str) -> str:
    p = presentation.lower()
    if "inhalador" in p:
        return ('<rect x="262" y="150" width="34" height="62" rx="8" fill="#fff" opacity=".9"/>'
                '<rect x="244" y="196" width="34" height="22" rx="6" fill="#fff" opacity=".9"/>')
    if "lapicero" in p:
        return '<rect x="226" y="176" width="86" height="18" rx="9" fill="#fff" opacity=".9"/>'
    if "cápsula" in p or "capsula" in p:
        return ('<g transform="rotate(-30 270 180)"><rect x="236" y="164" width="70" height="32" rx="16" fill="#fff" opacity=".9"/>'
                '<rect x="271" y="164" width="35" height="32" rx="16" fill="#fff" opacity=".55"/></g>')
    return ('<circle cx="256" cy="172" r="20" fill="#fff" opacity=".9"/>'
            '<circle cx="292" cy="190" r="20" fill="#fff" opacity=".9"/>'
            '<line x1="242" y1="172" x2="270" y2="172" stroke="#000" stroke-opacity=".15" stroke-width="3"/>')


def placeholder_svg(med: sqlite3.Row) -> str:
    hue = _hue(med["name"])
    dark, light = f"hsl({hue} 55% 30%)", f"hsl({hue} 45% 94%)"
    name_lines = _wrap(med["name"], 14)
    name_svg = "".join(
        f'<text x="40" y="{300 + i * 38}" font-size="34" font-weight="700" fill="#14201D">{escape(line)}</text>'
        for i, line in enumerate(name_lines)
    )
    y_strength = 300 + len(name_lines) * 38 + 12
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 480" role="img">
<rect width="400" height="480" fill="{light}"/>
<rect x="20" y="20" width="360" height="440" rx="24" fill="#fff" stroke="{dark}" stroke-width="4"/>
<path d="M22 44a22 22 0 0 1 22-22h312a22 22 0 0 1 22 22v196H22z" fill="{dark}"/>
<text x="40" y="78" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="700" fill="#fff" letter-spacing="2">Rx</text>
{_form_icon(med["presentation"])}
<g font-family="Arial, Helvetica, sans-serif">
{name_svg}
<text x="40" y="{y_strength + 24}" font-size="40" font-weight="700" fill="{dark}">{escape(med["strength"])}</text>
<text x="40" y="430" font-size="22" fill="#3F4D48">{escape(med["presentation"])}</text>
</g>
</svg>"""
