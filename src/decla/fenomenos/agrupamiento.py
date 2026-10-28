"""Agrupamiento: HDBSCAN (método principal) + 3 contrastes — NMF, k-means, aglomerativo
jerárquico (plan_trabajo.md §7.1 pasos 3 y 5; Fase 6, Bloque 2C).

Ningún método decide su mejor configuración solo por su métrica interna (silueta, etc.): la
selección final se valida con estabilidad entre corridas (`decla.fenomenos.estabilidad`), no
solo aquí — esta capa expone los candidatos, no la decisión final.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.cluster import HDBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

RUIDO = -1


@dataclass(frozen=True)
class ResultadoAgrupamiento:
    metodo: str
    etiquetas: np.ndarray
    parametros: dict[str, Any] = field(default_factory=dict)


def agrupar_hdbscan(
    matriz: np.ndarray, min_cluster_size: int, min_samples: int, metrica: str = "euclidean"
) -> ResultadoAgrupamiento:
    modelo = HDBSCAN(
        min_cluster_size=min_cluster_size, min_samples=min_samples, metric=metrica, copy=False
    )
    etiquetas = modelo.fit_predict(matriz)
    return ResultadoAgrupamiento(
        "hdbscan", etiquetas, {"min_cluster_size": min_cluster_size, "min_samples": min_samples}
    )


def barrer_hdbscan(
    matriz: np.ndarray,
    min_cluster_size_barrido: list[int],
    min_samples_barrido: list[int],
    metrica: str = "euclidean",
) -> list[ResultadoAgrupamiento]:
    """Un resultado por cada combinación razonable del barrido (min_samples <= min_cluster_size,
    convención recomendada de HDBSCAN); `decla.fenomenos.estabilidad` elige entre ellos.
    """
    resultados = []
    for tamano_minimo in min_cluster_size_barrido:
        for muestras_minimas in min_samples_barrido:
            if muestras_minimas > tamano_minimo:
                continue
            resultados.append(
                agrupar_hdbscan(matriz, tamano_minimo, muestras_minimas, metrica)
            )
    return resultados


def elegir_kmeans_por_silueta(
    matriz: np.ndarray, k_minimo: int, k_maximo: int, semilla: int
) -> ResultadoAgrupamiento:
    k_maximo_valido = min(k_maximo, matriz.shape[0] - 1)
    mejor_etiquetas: np.ndarray | None = None
    mejor_k = 1
    mejor_score = -2.0

    for k in range(k_minimo, k_maximo_valido + 1):
        modelo = KMeans(n_clusters=k, random_state=semilla, n_init=10)
        etiquetas = modelo.fit_predict(matriz)
        if len(set(etiquetas.tolist())) < 2:
            continue
        score = silhouette_score(matriz, etiquetas)
        if score > mejor_score:
            mejor_score, mejor_k, mejor_etiquetas = score, k, etiquetas

    if mejor_etiquetas is None:
        return ResultadoAgrupamiento("kmeans", np.zeros(matriz.shape[0], dtype=int), {"k": 1})
    return ResultadoAgrupamiento(
        "kmeans", mejor_etiquetas, {"k": mejor_k, "silueta": round(mejor_score, 4)}
    )


def construir_tfidf(lemas_por_relato: list[str], max_features: int) -> np.ndarray:
    """`lemas_por_relato`: un string por relato con los lemas separados por espacio (no
    embeddings: NMF exige una matriz no negativa).
    """
    vectorizador = TfidfVectorizer(max_features=max_features)
    matriz = vectorizador.fit_transform(lemas_por_relato)
    return np.asarray(matriz.toarray())


def agrupar_nmf(
    matriz_tfidf: np.ndarray, n_componentes: int, semilla: int
) -> ResultadoAgrupamiento:
    n_componentes_valido = min(n_componentes, matriz_tfidf.shape[0], matriz_tfidf.shape[1])
    modelo = NMF(
        n_components=max(1, n_componentes_valido),
        random_state=semilla,
        init="nndsvda",
        max_iter=500,
    )
    pesos = modelo.fit_transform(matriz_tfidf)
    etiquetas = pesos.argmax(axis=1)
    return ResultadoAgrupamiento("nmf", etiquetas, {"n_componentes": n_componentes_valido})


def agrupar_agglomerative(
    matriz: np.ndarray, n_clusters: int, linkage: str, metrica: str
) -> ResultadoAgrupamiento:
    n_clusters_valido = min(n_clusters, matriz.shape[0])
    modelo = AgglomerativeClustering(
        n_clusters=n_clusters_valido, linkage=linkage, metric=metrica
    )
    etiquetas = modelo.fit_predict(matriz)
    return ResultadoAgrupamiento(
        "agglomerative", etiquetas, {"n_clusters": n_clusters_valido, "linkage": linkage}
    )
