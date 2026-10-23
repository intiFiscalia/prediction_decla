"""Normalización de identificadores (CLAUDE.md §4.9, §4.10; plan_trabajo.md Fase 3.3).

Los identificadores se tratan siempre como texto, nunca como número: un lector que los convirtió
a flotante deja un sufijo ".0" que aquí se retira. `CASO_NOTICIA` se descompone según la
hipótesis confirmada en I0 con DIVIPOLA real (cod_mpio(5) + entidad(2) + unidad(5) + año(4) +
consecutivo(5), ADR correspondiente; prefijo DANE validado al 100 % sobre el dataset real).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATRON_SOLO_DIGITOS = re.compile(r"^\d+$")


def limpiar_identificador(valor: str | None) -> str | None:
    """Quita el sufijo ``.0`` que deja un lector que convirtió el identificador a flotante."""
    if valor is None:
        return None
    return valor[:-2] if valor.endswith(".0") else valor


@dataclass
class CasoNoticiaDescompuesto:
    valor_limpio: str | None
    valido_21_digitos: bool
    cn_dane: str | None = None
    cn_entidad: str | None = None
    cn_unidad: str | None = None
    cn_anio: str | None = None
    cn_consecutivo: str | None = None


def descomponer_caso_noticia(valor: str | None) -> CasoNoticiaDescompuesto:
    valor_limpio = limpiar_identificador(valor)
    if (
        not valor_limpio
        or not _PATRON_SOLO_DIGITOS.match(valor_limpio)
        or len(valor_limpio) != 21
    ):
        return CasoNoticiaDescompuesto(valor_limpio=valor_limpio, valido_21_digitos=False)
    return CasoNoticiaDescompuesto(
        valor_limpio=valor_limpio,
        valido_21_digitos=True,
        cn_dane=valor_limpio[:5],
        cn_entidad=valor_limpio[5:7],
        cn_unidad=valor_limpio[7:12],
        cn_anio=valor_limpio[12:16],
        cn_consecutivo=valor_limpio[16:21],
    )
