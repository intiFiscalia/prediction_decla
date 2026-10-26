"""Negación, hipótesis y atribución tipo NegEx en español (plan_trabajo.md §6.1 paso 8;
CLAUDE.md §4.22). Marca la polaridad de un span según los disparadores que aparecen en una
ventana de palabras alrededor de él: una mención dentro del alcance de "no se halló" no describe
un hecho afirmado, aunque el fragmento coincida con un patrón o gazetteer (consumido en 2B).

Negación e hipótesis dominan sobre atribución si ambas aparecen en la ventana: lo relevante para
no sobre-contar es si el hecho se afirma o no, no quién lo dice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

AFIRMADA = "afirmada"
NEGADA = "negada"
HIPOTETICA = "hipotetica"
ATRIBUIDA = "atribuida"


@dataclass(frozen=True)
class DisparadorEncontrado:
    tipo: str
    texto: str
    inicio: int
    fin: int


def _construir_patron(disparadores: list[str]) -> re.Pattern[str]:
    alternativas = "|".join(re.escape(d) for d in disparadores)
    return re.compile(alternativas, re.IGNORECASE)


def _localizar_disparadores(
    texto: str,
    disparadores_negacion: list[str],
    disparadores_hipotesis: list[str],
    disparadores_atribucion: list[str],
) -> list[DisparadorEncontrado]:
    especificacion = (
        (NEGADA, disparadores_negacion),
        (HIPOTETICA, disparadores_hipotesis),
        (ATRIBUIDA, disparadores_atribucion),
    )
    encontrados = []
    for tipo, disparadores in especificacion:
        if not disparadores:
            continue
        patron = _construir_patron(disparadores)
        for m in patron.finditer(texto):
            encontrados.append(DisparadorEncontrado(tipo, m.group(), m.start(), m.end()))
    return encontrados


def _dentro_de_ventana(
    disparador: DisparadorEncontrado,
    span_inicio: int,
    span_fin: int,
    texto: str,
    ventana_tokens: int,
) -> bool:
    if disparador.fin <= span_inicio:
        brecha = texto[disparador.fin : span_inicio]
    elif disparador.inicio >= span_fin:
        brecha = texto[span_fin : disparador.inicio]
    else:
        brecha = ""
    return len(brecha.split()) <= ventana_tokens


def clasificar_polaridad(
    texto: str,
    span_inicio: int,
    span_fin: int,
    disparadores_negacion: list[str],
    disparadores_hipotesis: list[str],
    disparadores_atribucion: list[str],
    ventana_tokens: int = 8,
) -> str:
    """Clasifica la polaridad de `texto[span_inicio:span_fin]` según los disparadores en una
    ventana de `ventana_tokens` palabras antes o después del span. Prioridad si hay varios:
    negada > hipotetica > atribuida > afirmada.
    """
    disparadores = _localizar_disparadores(
        texto, disparadores_negacion, disparadores_hipotesis, disparadores_atribucion
    )
    en_ventana = [
        d
        for d in disparadores
        if _dentro_de_ventana(d, span_inicio, span_fin, texto, ventana_tokens)
    ]
    tipos_en_ventana = {d.tipo for d in en_ventana}
    for prioridad in (NEGADA, HIPOTETICA, ATRIBUIDA):
        if prioridad in tipos_en_ventana:
            return prioridad
    return AFIRMADA
