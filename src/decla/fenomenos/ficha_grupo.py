"""Ficha automática por grupo descubierto (plan_trabajo.md §7.1 paso 4; Fase 6, Bloque 2C):
términos c-TF-IDF, menciones dominantes, distribución por metadatos (agregada, nunca para
formar el grupo — solo para describirlo), medoides/bordes, e indicador de dominancia de
plantilla (proxy barato del riesgo documentado en ADR 0010).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer


def calcular_c_tfidf(
    lemas_por_grupo: dict[Any, str], top_n: int = 10
) -> dict[Any, list[tuple[str, float]]]:
    """c-TF-IDF estilo BERTopic: frecuencia de término DENTRO del grupo (no del documento
    individual), ponderada por qué tan concentrado está ese término en pocos grupos.
    `lemas_por_grupo[g]` es un solo string con todos los lemas del grupo `g`, separados por
    espacio (ya en minúscula natural, normalización conservadora de 2A).
    """
    grupos = sorted(lemas_por_grupo, key=str)
    documentos = [lemas_por_grupo[grupo] for grupo in grupos]
    if not documentos or not any(documentos):
        return {grupo: [] for grupo in grupos}

    vectorizador = CountVectorizer()
    conteos = vectorizador.fit_transform(documentos).toarray().astype(float)
    terminos = vectorizador.get_feature_names_out()

    palabras_por_grupo = conteos.sum(axis=1, keepdims=True)
    palabras_por_grupo[palabras_por_grupo == 0] = 1.0
    frecuencia_relativa = conteos / palabras_por_grupo

    frecuencia_termino_entre_grupos = conteos.sum(axis=0)
    promedio_palabras_por_grupo = float(palabras_por_grupo.mean())
    idf = np.log(1 + promedio_palabras_por_grupo / np.maximum(frecuencia_termino_entre_grupos, 1))

    c_tfidf = frecuencia_relativa * idf

    resultado: dict[Any, list[tuple[str, float]]] = {}
    for i, grupo in enumerate(grupos):
        indices_top = np.argsort(-c_tfidf[i])[:top_n]
        resultado[grupo] = [
            (str(terminos[j]), round(float(c_tfidf[i, j]), 4))
            for j in indices_top
            if c_tfidf[i, j] > 0
        ]
    return resultado


def menciones_dominantes(
    menciones_del_grupo: list[dict[str, Any]], top_n: int = 10
) -> list[tuple[str, str, float]]:
    """`(categoria, valor_normalizado, proporción)` ordenado por frecuencia, sobre el total de
    menciones del grupo (no sobre el total de relatos: un relato puede aportar varias).
    """
    total = len(menciones_del_grupo)
    if total == 0:
        return []
    conteos = Counter(
        (m["categoria"], m.get("valor_normalizado")) for m in menciones_del_grupo
    )
    return [
        (categoria, str(valor), round(conteo / total, 4))
        for (categoria, valor), conteo in conteos.most_common(top_n)
    ]


def distribucion_metadata(
    metadata_del_grupo: list[dict[str, Any]], columna: str
) -> dict[str, int]:
    conteos = Counter(str(fila.get(columna)) for fila in metadata_del_grupo)
    return dict(conteos.most_common())


def _distancias_a_centroide(vectores: dict[str, list[float]]) -> dict[str, float]:
    arreglo = {uid: np.array(vector) for uid, vector in vectores.items()}
    centroide = np.mean(list(arreglo.values()), axis=0)
    return {uid: float(np.linalg.norm(vector - centroide)) for uid, vector in arreglo.items()}


def seleccionar_medoides_y_bordes(
    vectores_grupo: dict[str, list[float]], n_medoides: int = 10, n_bordes: int = 5
) -> tuple[list[str], list[str]]:
    """Medoides = los más cercanos al centroide del grupo (representativos); bordes = los más
    lejanos QUE SIGUEN perteneciendo al grupo (casos límite, útiles para el taller de revisión).
    """
    if not vectores_grupo:
        return [], []
    distancias = _distancias_a_centroide(vectores_grupo)
    ordenados = sorted(distancias, key=lambda uid: distancias[uid])
    medoides = ordenados[:n_medoides]
    bordes = ordenados[-n_bordes:] if n_bordes > 0 else []
    return medoides, [uid for uid in bordes if uid not in medoides]


def indicador_dominancia_plantilla(
    metodos_segmentacion_del_grupo: list[str], valor_sin_marcador: str = "sin_marcador"
) -> float:
    """Proporción del grupo cuyo relato no tuvo marcador de segmentación (CLAUDE.md ADR 0010):
    un valor alto sugiere que el grupo puede estar dominado por plantilla institucional en vez
    de por un fenómeno real, y debe revisarse con cautela en el taller.
    """
    if not metodos_segmentacion_del_grupo:
        return 0.0
    return round(
        sum(1 for m in metodos_segmentacion_del_grupo if m == valor_sin_marcador)
        / len(metodos_segmentacion_del_grupo),
        4,
    )


def indicador_dominancia_unidad(unidades_del_grupo: list[str]) -> float:
    """Proporción del grupo que pertenece a la unidad (despacho) más frecuente: un valor alto
    sugiere que el grupo puede reflejar la plantilla de una sola unidad, no un fenómeno
    transversal (plan_trabajo.md §7, riesgo documentado).
    """
    if not unidades_del_grupo:
        return 0.0
    _, conteo = Counter(unidades_del_grupo).most_common(1)[0]
    return round(conteo / len(unidades_del_grupo), 4)


@dataclass(frozen=True)
class FichaGrupo:
    grupo_id: str
    n_miembros: int
    metodo: str = ""
    terminos_c_tfidf: list[tuple[str, float]] = field(default_factory=list)
    menciones_dominantes: list[tuple[str, str, float]] = field(default_factory=list)
    distribucion_delito: dict[str, int] = field(default_factory=dict)
    distribucion_titulo_cp: dict[str, int] = field(default_factory=dict)
    distribucion_unidad: dict[str, int] = field(default_factory=dict)
    distribucion_departamento: dict[str, int] = field(default_factory=dict)
    distribucion_anio: dict[str, int] = field(default_factory=dict)
    medoides: list[str] = field(default_factory=list)
    bordes: list[str] = field(default_factory=list)
    dominancia_plantilla: float = 0.0
    dominancia_unidad: float = 0.0
