"""Enmascaramiento de datos personales (plan_trabajo.md §6.1 paso 7; CLAUDE.md §4.24).

Reemplaza con marcadores tipados: `[DOC]` (cédula/NIT), `[TEL]`, `[CORREO]`, `[PLACA]`,
`[DIRECCION]` por regex de alta precisión (formato muy regular en Colombia), y `[PERSONA]` por
NER-PER de spaCy sobre lo que las reglas no cubrieron. La versión enmascarada es la única vista
analítica (embeddings, buscador semántico, c-TF-IDF en 2C); el texto sin enmascarar nunca sale de
`texto.relato_procesado` hacia el resto del pipeline.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from decla.texto.offsets import ConstructorTextoConOffsets, MapaOffsets
from decla.texto.patrones_regex import (
    Coincidencia,
    extraer_cedulas,
    extraer_correos,
    extraer_nit,
    extraer_placas,
    extraer_telefonos,
)
from decla.texto.pipeline_spacy import analizar

MARCADOR_POR_CATEGORIA = {
    "cedula": "[DOC]",
    "nit": "[DOC]",
    "telefono": "[TEL]",
    "correo": "[CORREO]",
    "placa": "[PLACA]",
    "direccion": "[DIRECCION]",
    "PER": "[PERSONA]",
}

PATRON_DIRECCION = re.compile(
    r"\b(?:calle|carrera|avenida|diagonal|transversal|cra\.?|cl\.?|kr\.?|tv\.?|dg\.?|av\.?)\s*"
    r"\d{1,3}\s*[a-zA-Z]?\s*(?:bis)?\s*#?\s*-?\s*\d{1,3}\s*(?:-\s*\d{1,3})?\b",
    re.IGNORECASE,
)


@dataclass
class ResultadoEnmascaramiento:
    texto_enmascarado: str
    conteos_por_tipo: dict[str, int]
    mapa_offsets: MapaOffsets


def extraer_direcciones(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia("direccion", m.group(), m.start(), m.end())
        for m in PATRON_DIRECCION.finditer(texto)
    ]


def _coincidencias_regex(texto: str) -> list[Coincidencia]:
    return (
        extraer_cedulas(texto)
        + extraer_nit(texto)
        + extraer_telefonos(texto)
        + extraer_correos(texto)
        + extraer_placas(texto)
        + extraer_direcciones(texto)
    )


def _coincidencias_personas(texto: str) -> list[Coincidencia]:
    doc = analizar(texto)
    return [
        Coincidencia("PER", ent.text, ent.start_char, ent.end_char)
        for ent in doc.ents
        if ent.label_ == "PER"
    ]


def _resolver_solapes(coincidencias: list[Coincidencia]) -> list[Coincidencia]:
    """Si dos coincidencias se solapan, prioriza la que empieza antes y, en caso de empate, la
    más larga (más específica: p. ej. una dirección completa sobre un número suelto).
    """
    ordenadas = sorted(coincidencias, key=lambda c: (c.inicio, -(c.fin - c.inicio)))
    aceptadas: list[Coincidencia] = []
    fin_max = -1
    for c in ordenadas:
        if c.inicio >= fin_max:
            aceptadas.append(c)
            fin_max = c.fin
    return aceptadas


def enmascarar(texto: str | None) -> ResultadoEnmascaramiento:
    if not texto:
        return ResultadoEnmascaramiento(texto or "", {}, MapaOffsets())

    coincidencias = _resolver_solapes(_coincidencias_regex(texto) + _coincidencias_personas(texto))

    constructor = ConstructorTextoConOffsets()
    conteos: Counter[str] = Counter()
    cursor = 0
    for coincidencia in coincidencias:
        constructor.agregar(texto[cursor : coincidencia.inicio], cursor, coincidencia.inicio)
        marcador = MARCADOR_POR_CATEGORIA[coincidencia.categoria]
        constructor.agregar(marcador, coincidencia.inicio, coincidencia.fin)
        conteos[marcador] += 1
        cursor = coincidencia.fin
    constructor.agregar(texto[cursor:], cursor, len(texto))

    texto_final, mapa = constructor.construir()
    return ResultadoEnmascaramiento(texto_final, dict(conteos), mapa)
