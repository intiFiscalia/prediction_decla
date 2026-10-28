import numpy as np

from decla.fenomenos.reduccion import reducir_dimension


def _datos_sinteticos() -> np.ndarray:
    rng = np.random.default_rng(0)
    return np.vstack([rng.normal(loc=i * 5, scale=0.5, size=(10, 20)) for i in range(3)])


def test_reducir_dimension_forma_de_salida() -> None:
    datos = _datos_sinteticos()
    resultado = reducir_dimension(
        datos, n_componentes=5, n_vecinos=15, metrica="cosine", semilla=42
    )
    assert resultado.shape == (30, 5)


def test_reducir_dimension_es_deterministico_con_la_misma_semilla() -> None:
    datos = _datos_sinteticos()
    r1 = reducir_dimension(datos, n_componentes=5, n_vecinos=15, metrica="cosine", semilla=42)
    r2 = reducir_dimension(datos, n_componentes=5, n_vecinos=15, metrica="cosine", semilla=42)
    assert np.allclose(r1, r2)


def test_reducir_dimension_con_pocos_puntos_no_falla() -> None:
    # n_vecinos (15) > n_puntos - 1: debe recortarse, no lanzar error.
    datos = np.random.default_rng(1).normal(size=(5, 10))
    resultado = reducir_dimension(datos, n_componentes=2, n_vecinos=15, metrica="cosine", semilla=1)
    assert resultado.shape == (5, 2)
