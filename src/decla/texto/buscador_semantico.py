"""Buscador semántico de relatos (plan_trabajo.md §7.3; CLAUDE.md §4.20).

Dada una consulta (texto libre o un relato de ejemplo) y un corpus de vectores ya calculados
(`texto.embeddings_relato`, sobre texto enmascarado — nunca sobre el original), devuelve los
`registro_uid` más similares por coseno con su puntaje. Esta función nunca decide qué texto
mostrar: solo devuelve identificadores y similitud; quien la llama (CLI, app) es responsable de
recuperar y enmascarar lo que se despliega.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from decla.texto.embeddings import PREFIJO_CONSULTA_POR_MODELO, cargar_modelo_embeddings


@dataclass(frozen=True)
class ResultadoBusqueda:
    registro_uid: str
    similitud: float


def _normalizar(vector: np.ndarray) -> np.ndarray:
    norma = np.linalg.norm(vector)
    return vector / norma if norma > 0 else vector


def vector_de_consulta(texto_consulta: str, nombre_modelo: str) -> list[float]:
    """Usa el prefijo "query:" en los modelos que lo requieren (p. ej. multilingual-e5-base),
    distinto del "passage:" que usan los relatos ya indexados en el corpus.
    """
    modelo = cargar_modelo_embeddings(nombre_modelo)
    prefijo = PREFIJO_CONSULTA_POR_MODELO.get(nombre_modelo, "")
    vector = modelo.encode([prefijo + texto_consulta], convert_to_numpy=True)[0]
    return list(vector.tolist())


def buscar_similares(
    vector_consulta: list[float],
    corpus: dict[str, list[float]],
    k: int = 10,
    excluir_uid: str | None = None,
) -> list[ResultadoBusqueda]:
    uids = [uid for uid in corpus if uid != excluir_uid]
    if not uids:
        return []

    consulta = _normalizar(np.array(vector_consulta, dtype=float))
    matriz = np.stack([_normalizar(np.array(corpus[uid], dtype=float)) for uid in uids])
    similitudes = matriz @ consulta

    orden = np.argsort(-similitudes)[:k]
    return [ResultadoBusqueda(uids[i], round(float(similitudes[i]), 4)) for i in orden]
