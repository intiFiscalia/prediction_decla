"""Reparación de codificación mojibake como transformación real (CLAUDE.md §4.15; Fase 3.3).

Reusa `decla.calidad.relatos.tiene_mojibake/reparar_mojibake` (I0 solo diagnosticaba; aquí se
aplica de verdad). El texto original siempre queda intacto en `bronce`, nunca se sobreescribe.
"""

from __future__ import annotations

from dataclasses import dataclass

from decla.calidad.relatos import reparar_mojibake, tiene_mojibake


@dataclass
class TextoReparado:
    texto: str | None
    reparacion_codificacion: bool
    reparacion_fallida: bool


def reparar_texto(texto_original: str | None) -> TextoReparado:
    if texto_original is None:
        return TextoReparado(texto=None, reparacion_codificacion=False, reparacion_fallida=False)
    if not tiene_mojibake(texto_original):
        return TextoReparado(
            texto=texto_original, reparacion_codificacion=False, reparacion_fallida=False
        )
    reparado = reparar_mojibake(texto_original)
    if reparado is None:
        return TextoReparado(
            texto=texto_original, reparacion_codificacion=False, reparacion_fallida=True
        )
    return TextoReparado(texto=reparado, reparacion_codificacion=True, reparacion_fallida=False)
