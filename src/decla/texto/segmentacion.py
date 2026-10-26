"""Separación `contexto_denuncia` / `descripcion_hecho` (plan_trabajo.md §6.1 paso 3;
CLAUDE.md §4.21). Evita que los grupos de fenómenos (I2 bloque 2C) se formen por la plantilla de
la unidad que redacta en vez de por el hecho descrito.

No todo relato tiene las dos partes: algunos empiezan a mitad de contexto ("En cumplimiento de lo
anterior…", CLAUDE.md §4.21). Si no se encuentra ningún marcador de transición, el relato completo
queda como `descripcion_hecho` — nunca se inventa un corte que no hay evidencia de dónde poner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SIN_MARCADOR = "sin_marcador"
MARCADOR_DESCRIPCION_HECHO = "marcador_descripcion_hecho"
VACIO = "vacio"


@dataclass
class SegmentacionRelato:
    contexto_denuncia: str | None
    descripcion_hecho: str
    metodo: str
    marcador_usado: str | None


def _construir_patron(frases: list[str]) -> re.Pattern[str]:
    alternativas = "|".join(re.escape(frase) for frase in frases)
    return re.compile(alternativas, re.IGNORECASE)


def segmentar(texto: str | None, marcadores_descripcion_hecho: list[str]) -> SegmentacionRelato:
    if not texto:
        return SegmentacionRelato(
            contexto_denuncia=None, descripcion_hecho=texto or "", metodo=VACIO, marcador_usado=None
        )

    patron = _construir_patron(marcadores_descripcion_hecho)
    coincidencia = patron.search(texto)
    if coincidencia is None or coincidencia.start() == 0:
        return SegmentacionRelato(
            contexto_denuncia=None,
            descripcion_hecho=texto,
            metodo=SIN_MARCADOR,
            marcador_usado=None,
        )

    inicio = coincidencia.start()
    return SegmentacionRelato(
        contexto_denuncia=texto[:inicio].strip(),
        descripcion_hecho=texto[inicio:].strip(),
        metodo=MARCADOR_DESCRIPCION_HECHO,
        marcador_usado=coincidencia.group(),
    )


def calcular_cobertura(textos: list[str], marcadores_descripcion_hecho: list[str]) -> float:
    """Proporción de `textos` donde se identificó un corte explícito (no cuenta `vacio`)."""
    relevantes = [t for t in textos if t]
    if not relevantes:
        return 0.0
    n_con_corte = sum(
        1
        for t in relevantes
        if segmentar(t, marcadores_descripcion_hecho).metodo == MARCADOR_DESCRIPCION_HECHO
    )
    return n_con_corte / len(relevantes)
