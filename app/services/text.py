"""Utilidades de texto para búsquedas tolerantes (sin tildes, sin mayúsculas)."""

import unicodedata


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_marks.lower().split())
