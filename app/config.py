"""Configuración central. Todo valor ajustable vive aquí y se puede cambiar por variable de entorno.

Las variables se pueden poner en un archivo `.env` en la raíz del proyecto (vea `.env.example`).
Ninguna es obligatoria: todas tienen un valor por defecto. Una variable definida en el sistema
tiene prioridad sobre la del archivo `.env`.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Lee líneas CLAVE=valor; ignora vacías y comentarios (#). Sin dependencias externas."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


_load_env_file(BASE_DIR / ".env")


def _db_path() -> Path:
    # Una ruta relativa se toma desde la carpeta del proyecto, no desde donde se ejecute el comando.
    p = Path(os.getenv("MIRECETA_DB", BASE_DIR / "data" / "mireceta.db")).expanduser()
    return p if p.is_absolute() else BASE_DIR / p


@dataclass(frozen=True)
class Settings:
    db_path: Path = _db_path()
    timezone: ZoneInfo = ZoneInfo(os.getenv("MIRECETA_TZ", "America/Bogota"))

    # Sesión: larga, para no obligar a personas mayores a ingresar a cada rato.
    session_days: int = int(os.getenv("MIRECETA_SESSION_DAYS", "30"))
    cookie_secure: bool = os.getenv("MIRECETA_COOKIE_SECURE", "0") == "1"

    # PIN
    pin_length: int = 4
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # Reservas
    reservation_hold_hours: int = int(os.getenv("MIRECETA_HOLD_HOURS", "24"))
    preparation_minutes: int = int(os.getenv("MIRECETA_PREP_MINUTES", "15"))

    # Personal de la droguería: una sesión dura un turno de trabajo.
    staff_session_hours: int = int(os.getenv("MIRECETA_STAFF_SESSION_HOURS", "12"))
    staff_password_min: int = 6

    # Tiempo real (services/live.py)
    live_poll_seconds: float = float(os.getenv("MIRECETA_LIVE_POLL", "1.0"))
    live_stream_seconds: int = int(os.getenv("MIRECETA_LIVE_STREAM_SECONDS", "300"))

    # Búsqueda
    default_radius_km: float = 5.0
    low_stock_threshold: int = 5
    # Ubicación por defecto si el navegador no comparte la suya (centro de Bogotá).
    default_lat: float = 4.6486
    default_lng: float = -74.0628


settings = Settings()
