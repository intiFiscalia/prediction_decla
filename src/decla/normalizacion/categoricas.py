"""Unificación de catálogos categóricos (plan_trabajo.md Fase 3.3).

Cada valor normalizado conserva su original (CLAUDE.md §3.4: las reglas de limpieza nunca ocultan
el dato de origen). La unificación es solo ortográfica (mayúsculas, tildes, espacios); fusionar
categorías que son semánticamente distintas con nombres distintos exige una decisión de negocio,
no una regla de código.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

COLUMNAS_CATEGORICAS_A_UNIFICAR = [
    "ESTADO",
    "ETAPA",
    "TIPO_NOTICIA",
    "TIPO_DILIGENCIA",
    "ULTIMA_ACTUACION",
]


def normalizar_categoria(valor: str | None) -> str | None:
    if valor is None:
        return None
    texto = valor.strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split())


@dataclass
class CategoriaNormalizada:
    valor_orig: str | None
    valor_normalizado: str | None


def normalizar_fila_categoricas(
    fila: dict[str, str | None],
    columnas: list[str] = COLUMNAS_CATEGORICAS_A_UNIFICAR,
) -> dict[str, CategoriaNormalizada]:
    return {
        columna: CategoriaNormalizada(
            valor_orig=fila.get(columna),
            valor_normalizado=normalizar_categoria(fila.get(columna)),
        )
        for columna in columnas
    }
