import numpy as np
from sklearn.cluster import KMeans

from decla.fenomenos.agrupamiento import ResultadoAgrupamiento
from decla.fenomenos.estabilidad import (
    comparar_particiones,
    evaluar_estabilidad_bootstrap,
    porcentaje_ruido,
    precision_recuperacion_fenomeno,
)


def _agrupar_k3(matriz: np.ndarray, semilla: int) -> ResultadoAgrupamiento:
    etiquetas = KMeans(n_clusters=3, random_state=semilla, n_init=10).fit_predict(matriz)
    return ResultadoAgrupamiento("kmeans", etiquetas)


def test_porcentaje_ruido() -> None:
    assert porcentaje_ruido(np.array([-1, -1, 0, 1, 1])) == 0.4


def test_porcentaje_ruido_lista_vacia() -> None:
    assert porcentaje_ruido(np.array([])) == 0.0


def test_comparar_particiones_identicas() -> None:
    ari, nmi = comparar_particiones(np.array([0, 0, 1, 1]), np.array([0, 0, 1, 1]))
    assert ari == 1.0
    assert nmi == 1.0


def test_comparar_particiones_permutadas_siguen_siendo_la_misma_estructura() -> None:
    # Las etiquetas 0/1 intercambiadas describen la MISMA partición: ARI/NMI deben seguir en 1.0.
    ari, nmi = comparar_particiones(np.array([0, 0, 1, 1]), np.array([1, 1, 0, 0]))
    assert ari == 1.0
    assert nmi == 1.0


def test_precision_recuperacion_fenomeno() -> None:
    etiquetas = np.array([0, 0, 0, 1, 1])
    fenomenos = ["a", "a", "b", "c", "c"]
    assert precision_recuperacion_fenomeno(etiquetas, fenomenos) == 0.8


def test_precision_recuperacion_fenomeno_ignora_ruido() -> None:
    etiquetas = np.array([-1, 0, 0])
    fenomenos = ["x", "a", "a"]
    assert precision_recuperacion_fenomeno(etiquetas, fenomenos) == 1.0


def test_evaluar_estabilidad_bootstrap_estructura_clara_da_ari_alto() -> None:
    rng = np.random.default_rng(0)
    datos = np.vstack([rng.normal(loc=i * 10, scale=0.5, size=(30, 10)) for i in range(3)])
    resumen = evaluar_estabilidad_bootstrap(
        datos, _agrupar_k3, n_corridas=5, fraccion_submuestra=0.8, semilla_base=1
    )
    assert resumen.ari_promedio > 0.9
    assert resumen.n_corridas == 5


def test_evaluar_estabilidad_bootstrap_ruido_puro_da_ari_mas_bajo() -> None:
    rng = np.random.default_rng(0)
    datos_estructurados = np.vstack(
        [rng.normal(loc=i * 10, scale=0.5, size=(30, 10)) for i in range(3)]
    )
    datos_ruido = rng.normal(size=(90, 10))

    resumen_estructurado = evaluar_estabilidad_bootstrap(
        datos_estructurados, _agrupar_k3, n_corridas=5, fraccion_submuestra=0.8, semilla_base=1
    )
    resumen_ruido = evaluar_estabilidad_bootstrap(
        datos_ruido, _agrupar_k3, n_corridas=5, fraccion_submuestra=0.8, semilla_base=1
    )
    assert resumen_ruido.ari_promedio < resumen_estructurado.ari_promedio
