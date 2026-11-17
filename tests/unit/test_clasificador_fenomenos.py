import numpy as np
import pytest

from decla.fenomenos.clasificador import (
    EntrenamientoBloqueado,
    entrenar_clasificador,
    evaluar_particion_temporal,
    exigir_cobertura_minima,
    predecir_codigos,
    verificar_cobertura_minima,
)


def test_verificar_cobertura_minima_identifica_faltantes() -> None:
    cobertura = {"a": 50, "b": 30}
    assert verificar_cobertura_minima(cobertura, minimo_por_codigo=50) == ["b"]


def test_verificar_cobertura_minima_vacio_si_todo_alcanza() -> None:
    cobertura = {"a": 60, "b": 50}
    assert verificar_cobertura_minima(cobertura, minimo_por_codigo=50) == []


def test_exigir_cobertura_minima_lanza_si_falta_algun_codigo() -> None:
    with pytest.raises(EntrenamientoBloqueado):
        exigir_cobertura_minima({"a": 10}, minimo_por_codigo=50)


def test_exigir_cobertura_minima_no_lanza_si_cumple() -> None:
    exigir_cobertura_minima({"a": 50}, minimo_por_codigo=50)


def _vectores_sinteticos_separables() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20260101)
    clase_a = rng.normal(loc=[5, 0], scale=0.2, size=(20, 2))
    clase_b = rng.normal(loc=[0, 5], scale=0.2, size=(20, 2))
    X = np.vstack([clase_a, clase_b])
    Y = np.zeros((40, 2), dtype=int)
    Y[:20, 0] = 1
    Y[20:, 1] = 1
    return X, Y


def test_entrenar_y_predecir_caso_claramente_separable() -> None:
    X, Y = _vectores_sinteticos_separables()
    modelo_fenomeno = entrenar_clasificador(X, Y, codigos=["a", "b"])

    predicciones = predecir_codigos(modelo_fenomeno, X[:1], confianza_minima=0.5)
    assert predicciones[0] == ["a"]

    predicciones_b = predecir_codigos(modelo_fenomeno, X[20:21], confianza_minima=0.5)
    assert predicciones_b[0] == ["b"]


def test_predecir_codigos_bajo_umbral_devuelve_vacio() -> None:
    X, Y = _vectores_sinteticos_separables()
    modelo_fenomeno = entrenar_clasificador(X, Y, codigos=["a", "b"])
    predicciones = predecir_codigos(modelo_fenomeno, X[:1], confianza_minima=0.999999)
    assert predicciones[0] == []


def test_evaluar_particion_temporal_separa_entrenamiento_y_prueba() -> None:
    X, Y = _vectores_sinteticos_separables()
    fechas = [f"2026-{(i % 10) + 1:02d}-01" for i in range(40)]

    metricas = evaluar_particion_temporal(X, Y, fechas, ["a", "b"], fecha_corte="2026-09-01")
    por_codigo = {m.codigo: m for m in metricas}
    assert por_codigo["a"].f1 >= 0.5
    assert por_codigo["b"].f1 >= 0.5
    assert por_codigo["a"].n_positivos_prueba > 0
