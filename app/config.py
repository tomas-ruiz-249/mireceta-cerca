"""Configuración central. Todo valor ajustable vive aquí y se puede cambiar por variable de entorno."""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("MIRECETA_DB", BASE_DIR / "data" / "mireceta.db"))
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
