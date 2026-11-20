"""Normalização textual compartilhada por coletores, revisão e pipeline."""

import re
import unicodedata

_SLUG_SEPARATOR = re.compile(r"[^a-z0-9]+")


def fold(value: str) -> str:
    """Remove acentos, aplica casefold e reduz espaços consecutivos."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_accents.casefold().split())


def slug(value: str) -> str:
    """Converte um texto em um slug estável em minúsculas, unido por hífens."""
    return _SLUG_SEPARATOR.sub("-", fold(value)).strip("-")
