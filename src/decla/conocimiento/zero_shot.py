"""Clasificación zero-shot de mecanismos/actividades por similitud de embeddings contra
definiciones semilla (plan_trabajo.md §6.2, fila "Actividades y mecanismos explícitos": lo que el
diccionario no cubre se clasifica "por similitud con definiciones semilla"). Mismo patrón que
`decla.conocimiento.sectores` (CIIU inferido): nunca fuerza una etiqueta si la confianza o el
margen no superan los umbrales de `config/umbrales.yaml`; por debajo del umbral queda
`"no_clasificado"`, un resultado legítimo (plan_trabajo.md §7.3), no un error.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from decla.comun.configuracion import cargar_yaml
from decla.texto.embeddings import MEDIA, calcular_embeddings_relato

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CATEGORIAS = RAIZ_PROYECTO / "config" / "categorias_menciones.yaml"

ORIGEN_INFERIDO = "inferido_modelo"
NO_CLASIFICADO = "no_clasificado"


@dataclass(frozen=True)
class DefinicionSemilla:
    codigo: str
    definicion: str


@dataclass(frozen=True)
class ClasificacionZeroShot:
    codigo: str | None
    confianza: float
    origen: str


def cargar_vocabulario(
    nombre_categoria: str, ruta: Path = RUTA_CATEGORIAS
) -> list[DefinicionSemilla]:
    contenido = cargar_yaml(ruta)
    for categoria in contenido["categorias"]:
        if categoria["nombre"] == nombre_categoria:
            return [
                DefinicionSemilla(entrada["codigo"], entrada["definicion"])
                for entrada in categoria.get("vocabulario", [])
                if "definicion" in entrada
            ]
    return []


def calcular_vectores_vocabulario(
    definiciones: list[DefinicionSemilla], nombre_modelo: str
) -> dict[str, list[float]]:
    vectores = {}
    for definicion in definiciones:
        embeddings = calcular_embeddings_relato(
            definicion.codigo, definicion.definicion, nombre_modelo
        )
        vector = next((e.vector for e in embeddings if e.agregacion == MEDIA), None)
        if vector is not None:
            vectores[definicion.codigo] = vector
    return vectores


def _similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    norma_a, norma_b = np.linalg.norm(a), np.linalg.norm(b)
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norma_a * norma_b))


def elegir_por_similitud(
    vector_fragmento: list[float],
    vectores_vocabulario: dict[str, list[float]],
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionZeroShot:
    """Parte pura: separada de `clasificar_fragmento` para probar el umbral con vectores
    sintéticos, sin pagar el costo de cargar un modelo de embeddings.
    """
    if len(vectores_vocabulario) < 2:
        return ClasificacionZeroShot(None, 0.0, ORIGEN_INFERIDO)

    arreglo = np.array(vector_fragmento)
    similitudes = sorted(
        (
            (codigo, _similitud_coseno(arreglo, np.array(vector)))
            for codigo, vector in vectores_vocabulario.items()
        ),
        key=lambda par: -par[1],
    )
    (codigo_top1, sim_top1), (_, sim_top2) = similitudes[0], similitudes[1]
    margen = sim_top1 - sim_top2

    if sim_top1 < confianza_minima or margen < margen_minimo_top2:
        return ClasificacionZeroShot(NO_CLASIFICADO, round(sim_top1, 4), ORIGEN_INFERIDO)
    return ClasificacionZeroShot(codigo_top1, round(sim_top1, 4), ORIGEN_INFERIDO)


def clasificar_fragmento(
    fragmento: str,
    vectores_vocabulario: dict[str, list[float]],
    nombre_modelo: str,
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionZeroShot:
    if not fragmento or not fragmento.strip():
        return ClasificacionZeroShot(None, 0.0, ORIGEN_INFERIDO)

    embeddings = calcular_embeddings_relato("_consulta_zero_shot", fragmento, nombre_modelo)
    vector = next((e.vector for e in embeddings if e.agregacion == MEDIA), None)
    if vector is None:
        return ClasificacionZeroShot(None, 0.0, ORIGEN_INFERIDO)

    return elegir_por_similitud(vector, vectores_vocabulario, confianza_minima, margen_minimo_top2)
