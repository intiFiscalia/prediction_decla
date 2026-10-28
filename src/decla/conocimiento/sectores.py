"""Sectores económicos CIIU Rev. 4 A.C. (plan_trabajo.md §6.4; Fase 5, Bloque 2B).

Explícito: diccionario de expresiones colombianas (`config/diccionarios/sectores_expresiones.yaml`).
Inferido: similitud de embeddings (modelo elegido en 2A, ADR 0005) contra las descripciones CIIU
(`data/referencia/ciiu.csv`); si la confianza o el margen entre el top-1 y el top-2 no superan
los umbrales de `config/umbrales.yaml`, el sector queda `"indeterminado"` — nunca se fuerza una
etiqueta (CLAUDE.md §2.3). El sector se asigna siempre al relato/mención, nunca a una persona u
organización (CLAUDE.md §2.3, plan §6.4): estas funciones no reciben ni devuelven ningún
identificador de persona.

**Riesgo sin validar (ADR 0010):** sobre los 346 relatos reales, el sector inferido dio 0 %
"indeterminado" en 335 casos — sospechosamente alto. Hipótesis de trabajo: el vector de entrada
sigue siendo casi el relato completo (la segmentación contexto/hecho solo se activa en 4,9 % de
los casos reales), así que el lenguaje institucional repetido puede estar dominando la similitud
en vez del sector real. No usar `categoria='sector'`/`origen='inferido_modelo'` como insumo de
indicadores sin la anotación humana pendiente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from decla.comun.configuracion import cargar_yaml
from decla.texto.embeddings import MEDIA, calcular_embeddings_relato

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CIIU = RAIZ_PROYECTO / "data" / "referencia" / "ciiu.csv"
RUTA_EXPRESIONES = RAIZ_PROYECTO / "config" / "diccionarios" / "sectores_expresiones.yaml"
RUTA_JERARQUIA = RAIZ_PROYECTO / "config" / "diccionarios" / "ciiu_jerarquia.yaml"

ORIGEN_EXPLICITO = "explicito_regla"
ORIGEN_INFERIDO = "inferido_modelo"
SECTOR_INDETERMINADO = "indeterminado"


@dataclass(frozen=True)
class EntradaCiiu:
    code: str
    description: str


@dataclass(frozen=True)
class ClasificacionSector:
    code: str | None
    division: str | None
    seccion: str | None
    confianza: float
    origen: str
    texto_evidencia: str | None


def cargar_ciiu(ruta: Path = RUTA_CIIU) -> list[EntradaCiiu]:
    df = pl.read_csv(ruta, infer_schema_length=0)
    return [EntradaCiiu(f["code"], f["description"]) for f in df.iter_rows(named=True)]


def cargar_expresiones(ruta: Path = RUTA_EXPRESIONES) -> list[dict[str, str]]:
    return list(cargar_yaml(ruta).get("expresiones", []))


def cargar_jerarquia_division_seccion(ruta: Path = RUTA_JERARQUIA) -> dict[str, str]:
    contenido = cargar_yaml(ruta)
    mapa: dict[str, str] = {}
    for seccion in contenido["secciones"]:
        for division in seccion["divisiones"]:
            mapa[division] = seccion["letra"]
    return mapa


def division_de_codigo(code: str) -> str:
    return code[:2]


def seccion_de_codigo(code: str, jerarquia: dict[str, str]) -> str | None:
    return jerarquia.get(division_de_codigo(code))


def clasificar_sector_explicito(
    texto: str, expresiones: list[dict[str, str]], jerarquia: dict[str, str]
) -> ClasificacionSector | None:
    """Devuelve `None` (no `SECTOR_INDETERMINADO`) si ninguna expresión aparece: significa que el
    diccionario no tiene evidencia, no que el sector sea indeterminado (eso es un resultado del
    camino inferido, con confianza medida).
    """
    for entrada in expresiones:
        patron = re.compile(re.escape(entrada["expresion"]), re.IGNORECASE)
        coincidencia = patron.search(texto)
        if coincidencia is None:
            continue
        code = entrada["code"]
        return ClasificacionSector(
            code=code,
            division=division_de_codigo(code),
            seccion=seccion_de_codigo(code, jerarquia),
            confianza=1.0,
            origen=ORIGEN_EXPLICITO,
            texto_evidencia=coincidencia.group(),
        )
    return None


def calcular_vectores_ciiu(
    entradas_ciiu: list[EntradaCiiu], nombre_modelo: str
) -> dict[str, list[float]]:
    """Vector por código CIIU (agregación media de su descripción). Costoso (una pasada de
    embeddings por las ~500 clases): se calcula una sola vez por lote, no por relato.
    """
    vectores = {}
    for entrada in entradas_ciiu:
        embeddings = calcular_embeddings_relato(entrada.code, entrada.description, nombre_modelo)
        vector = next((e.vector for e in embeddings if e.agregacion == MEDIA), None)
        if vector is not None:
            vectores[entrada.code] = vector
    return vectores


def _similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    norma_a, norma_b = np.linalg.norm(a), np.linalg.norm(b)
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norma_a * norma_b))


def elegir_sector_por_similitud(
    vector_texto: list[float],
    vectores_ciiu: dict[str, list[float]],
    jerarquia: dict[str, str],
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionSector:
    """Parte pura de `clasificar_sector_inferido`: separado para poder probar la lógica de
    umbral con vectores sintéticos, sin pagar el costo de cargar un modelo de embeddings.
    """
    if len(vectores_ciiu) < 2:
        return ClasificacionSector(None, None, None, 0.0, ORIGEN_INFERIDO, None)

    arreglo_texto = np.array(vector_texto)
    similitudes = sorted(
        (
            (code, _similitud_coseno(arreglo_texto, np.array(vector)))
            for code, vector in vectores_ciiu.items()
        ),
        key=lambda par: -par[1],
    )
    (code_top1, sim_top1), (_, sim_top2) = similitudes[0], similitudes[1]
    margen = sim_top1 - sim_top2

    if sim_top1 < confianza_minima or margen < margen_minimo_top2:
        return ClasificacionSector(
            SECTOR_INDETERMINADO, None, None, round(sim_top1, 4), ORIGEN_INFERIDO, None
        )

    return ClasificacionSector(
        code=code_top1,
        division=division_de_codigo(code_top1),
        seccion=seccion_de_codigo(code_top1, jerarquia),
        confianza=round(sim_top1, 4),
        origen=ORIGEN_INFERIDO,
        texto_evidencia=None,
    )


def clasificar_sector_inferido(
    texto: str,
    vectores_ciiu: dict[str, list[float]],
    nombre_modelo: str,
    jerarquia: dict[str, str],
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionSector:
    if not texto or not texto.strip() or len(vectores_ciiu) < 2:
        return ClasificacionSector(None, None, None, 0.0, ORIGEN_INFERIDO, None)

    embeddings = calcular_embeddings_relato("_consulta_sector", texto, nombre_modelo)
    vector_texto = next((e.vector for e in embeddings if e.agregacion == MEDIA), None)
    if vector_texto is None:
        return ClasificacionSector(None, None, None, 0.0, ORIGEN_INFERIDO, None)

    return elegir_sector_por_similitud(
        vector_texto, vectores_ciiu, jerarquia, confianza_minima, margen_minimo_top2
    )
