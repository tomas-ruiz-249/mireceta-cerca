"""Distancias y tiempos de viaje aproximados."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0
WALK_KMH = 4.0
CAR_KMH = 18.0  # tráfico urbano en Bogotá
WALKING_LIMIT_KM = 1.0


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def travel_text(km: float) -> str:
    if km <= WALKING_LIMIT_KM:
        minutes = max(1, round(km / WALK_KMH * 60))
        return f"{minutes} min caminando"
    minutes = max(1, round(km / CAR_KMH * 60))
    return f"{minutes} min en carro"


def distance_text(km: float) -> str:
    if km < 1:
        return f"{round(km * 1000 / 50) * 50} m"
    return f"{km:.1f} km".replace(".", ",")
