import numpy as np
from sklearn.metrics import adjusted_rand_score

from decla.fenomenos.agrupamiento import (
    agrupar_agglomerative,
    agrupar_hdbscan,
    agrupar_nmf,
    barrer_hdbscan,
    construir_tfidf,
    elegir_kmeans_por_silueta,
)


def _datos_tres_grupos() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    datos = np.vstack([rng.normal(loc=i * 10, scale=0.5, size=(15, 10)) for i in range(3)])
    verdad = np.repeat([0, 1, 2], 15)
    return datos, verdad


def test_agrupar_hdbscan_recupera_grupos_bien_separados() -> None:
    datos, verdad = _datos_tres_grupos()
    resultado = agrupar_hdbscan(datos, min_cluster_size=5, min_samples=3)
    assert adjusted_rand_score(verdad, resultado.etiquetas) == 1.0


def test_barrer_hdbscan_descarta_combinaciones_sin_sentido() -> None:
    resultados = barrer_hdbscan(
        np.zeros((5, 2)), min_cluster_size_barrido=[5], min_samples_barrido=[1, 10]
    )
    # min_samples=10 > min_cluster_size=5 se descarta; solo queda min_samples=1.
    assert len(resultados) == 1
    assert resultados[0].parametros == {"min_cluster_size": 5, "min_samples": 1}


def test_elegir_kmeans_por_silueta_recupera_k_correcto() -> None:
    datos, verdad = _datos_tres_grupos()
    resultado = elegir_kmeans_por_silueta(datos, k_minimo=2, k_maximo=10, semilla=1)
    assert resultado.parametros["k"] == 3
    assert adjusted_rand_score(verdad, resultado.etiquetas) == 1.0


def test_agrupar_agglomerative_recupera_grupos() -> None:
    datos, verdad = _datos_tres_grupos()
    resultado = agrupar_agglomerative(datos, n_clusters=3, linkage="average", metrica="euclidean")
    assert adjusted_rand_score(verdad, resultado.etiquetas) == 1.0


def test_agrupar_nmf_recupera_grupos_tematicos() -> None:
    textos = (
        ["perro gato perro animal"] * 15
        + ["carro moto vehiculo transporte"] * 15
        + ["dinero banco finanzas pago"] * 15
    )
    verdad = np.repeat([0, 1, 2], 15)
    tfidf = construir_tfidf(textos, max_features=50)
    resultado = agrupar_nmf(tfidf, n_componentes=3, semilla=1)
    assert adjusted_rand_score(verdad, resultado.etiquetas) == 1.0


def test_agrupar_nmf_recorta_n_componentes_a_lo_disponible() -> None:
    textos = ["una sola palabra"] * 3
    tfidf = construir_tfidf(textos, max_features=50)
    resultado = agrupar_nmf(tfidf, n_componentes=20, semilla=1)
    assert resultado.parametros["n_componentes"] <= 3
