"""Cómo se presenta un medicamento hacia afuera (API). Un solo lugar para todas las pantallas."""

from collections.abc import Mapping

from . import images


def to_dict(m: Mapping) -> dict:
    return {
        "id": m["id"],
        "name": m["name"],
        "strength": m["strength"],
        "presentation": m["presentation"],
        "image_url": images.url_for(m),
        "has_photo": bool(m["image"]),
    }
