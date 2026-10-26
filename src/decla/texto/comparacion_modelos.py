"""Comparación de modelos de embeddings sobre fixtures (plan_trabajo.md §5.2, §6.1 paso 8;
CLAUDE.md §4.20). Mide precisión@k: para cada relato sintético, ¿cuántos de sus k vecinos más
cercanos por coseno comparten el mismo `fenomeno_plantado`? Es una medida indicativa sobre datos
sintéticos (cada relato describe un fenómeno y un estilo de redacción plantados a propósito para
poder medir esto); la elección definitiva de modelo también pondera los pares reales calificados
por analistas (`herramienta_anotacion_pares.py`), que esta función no sustituye.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from decla.texto.embeddings import MEDIA, calcular_embeddings_relato


@dataclass(frozen=True)
class RelatoEtiquetado:
    registro_uid: str
    texto: str
    fenomeno_plantado: str


def _vector_normalizado(vector: list[float]) -> np.ndarray:
    arreglo = np.array(vector, dtype=float)
    norma = np.linalg.norm(arreglo)
    return arreglo / norma if norma > 0 else arreglo


def calcular_matriz_embeddings(
    relatos: list[RelatoEtiquetado], nombre_modelo: str, agregacion: str = MEDIA
) -> dict[str, np.ndarray]:
    vectores: dict[str, np.ndarray] = {}
    for relato in relatos:
        embeddings = calcular_embeddings_relato(relato.registro_uid, relato.texto, nombre_modelo)
        for embedding in embeddings:
            if embedding.agregacion == agregacion:
                vectores[relato.registro_uid] = _vector_normalizado(embedding.vector)
    return vectores


def precision_en_k(
    relatos: list[RelatoEtiquetado], vectores: dict[str, np.ndarray], k: int = 5
) -> float:
    """Entre los `k` vecinos más cercanos de cada relato (excluyéndose a sí mismo), la
    proporción que comparte su `fenomeno_plantado`, promediada sobre todos los relatos.
    """
    etiqueta_por_uid = {r.registro_uid: r.fenomeno_plantado for r in relatos}
    uids = [r.registro_uid for r in relatos if r.registro_uid in vectores]
    if len(uids) < 2:
        return 0.0

    matriz = np.stack([vectores[uid] for uid in uids])
    similitudes = matriz @ matriz.T

    aciertos_totales = 0
    comparaciones_totales = 0
    for i, uid in enumerate(uids):
        orden = np.argsort(-similitudes[i])
        vecinos = [j for j in orden if j != i][:k]
        etiqueta_objetivo = etiqueta_por_uid[uid]
        aciertos_totales += sum(
            1 for j in vecinos if etiqueta_por_uid[uids[j]] == etiqueta_objetivo
        )
        comparaciones_totales += len(vecinos)

    return aciertos_totales / comparaciones_totales if comparaciones_totales else 0.0


@dataclass(frozen=True)
class ResultadoComparacionModelo:
    nombre_modelo: str
    agregacion: str
    precision_en_k: float
    k: int
    n_relatos: int


def comparar_modelos(
    relatos: list[RelatoEtiquetado],
    nombres_modelos: list[str],
    k: int = 5,
    agregacion: str = MEDIA,
) -> list[ResultadoComparacionModelo]:
    resultados = []
    for nombre_modelo in nombres_modelos:
        vectores = calcular_matriz_embeddings(relatos, nombre_modelo, agregacion)
        precision = precision_en_k(relatos, vectores, k)
        resultados.append(
            ResultadoComparacionModelo(
                nombre_modelo, agregacion, round(precision, 4), k, len(vectores)
            )
        )
    return resultados
