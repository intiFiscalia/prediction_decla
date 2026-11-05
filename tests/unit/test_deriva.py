from decla.comun.deriva import ks_dos_muestras, psi_categorico, psi_numerico


def test_psi_numerico_misma_distribucion_es_bajo() -> None:
    base = list(range(100))
    nuevo = list(range(100))
    assert psi_numerico(base, nuevo) < 0.1


def test_psi_numerico_distribucion_desplazada_es_alto() -> None:
    base = list(range(100))
    nuevo = [x + 500 for x in range(100)]  # desplazamiento fuerte, sin solape
    assert psi_numerico(base, nuevo) > 0.25


def test_psi_numerico_base_constante_no_falla() -> None:
    assert psi_numerico([5.0] * 20, [5.0, 6.0, 7.0]) == 0.0


def test_psi_numerico_sin_datos_es_nan() -> None:
    import math

    assert math.isnan(psi_numerico([], [1.0, 2.0]))


def test_psi_categorico_misma_proporcion_es_bajo() -> None:
    base = {"a": 50, "b": 50}
    nuevo = {"a": 48, "b": 52}
    assert psi_categorico(base, nuevo) < 0.1


def test_psi_categorico_categoria_nueva_dispara_deriva() -> None:
    base = {"a": 100}
    nuevo = {"a": 50, "b": 50}  # categoría "b" nunca vista en la base
    assert psi_categorico(base, nuevo) > 0.25


def test_ks_dos_muestras_misma_distribucion_p_alto() -> None:
    import numpy as np

    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 200).tolist()
    nuevo = rng.normal(0, 1, 200).tolist()
    resultado = ks_dos_muestras(base, nuevo)
    assert resultado["p"] > 0.05


def test_ks_dos_muestras_distribuciones_distintas_p_bajo() -> None:
    import numpy as np

    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 200).tolist()
    nuevo = rng.normal(10, 1, 200).tolist()
    resultado = ks_dos_muestras(base, nuevo)
    assert resultado["p"] < 0.01


def test_ks_dos_muestras_sin_datos_no_falla() -> None:
    assert ks_dos_muestras([], [1.0]) == {"estadistico": None, "p": None}
