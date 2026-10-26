import numpy as np

from decla.texto.comparacion_modelos import (
    RelatoEtiquetado,
    comparar_modelos,
    precision_en_k,
)

MODELO_RAPIDO = "paraphrase-multilingual-mpnet-base-v2"


def test_precision_en_k_con_vectores_perfectamente_separados() -> None:
    relatos = [
        RelatoEtiquetado("u1", "", "fenomeno_a"),
        RelatoEtiquetado("u2", "", "fenomeno_a"),
        RelatoEtiquetado("u3", "", "fenomeno_b"),
        RelatoEtiquetado("u4", "", "fenomeno_b"),
    ]
    vectores = {
        "u1": np.array([1.0, 0.0]),
        "u2": np.array([0.99, 0.01]),
        "u3": np.array([0.0, 1.0]),
        "u4": np.array([0.01, 0.99]),
    }
    assert precision_en_k(relatos, vectores, k=1) == 1.0


def test_precision_en_k_con_vectores_mezclados() -> None:
    relatos = [
        RelatoEtiquetado("u1", "", "fenomeno_a"),
        RelatoEtiquetado("u2", "", "fenomeno_b"),
        RelatoEtiquetado("u3", "", "fenomeno_a"),
        RelatoEtiquetado("u4", "", "fenomeno_b"),
    ]
    # u1 y u2 son casi idénticos (fenómenos distintos): el vecino más cercano de u1 es u2.
    vectores = {
        "u1": np.array([1.0, 0.0]),
        "u2": np.array([0.999, 0.001]),
        "u3": np.array([0.0, 1.0]),
        "u4": np.array([0.001, 0.999]),
    }
    assert precision_en_k(relatos, vectores, k=1) == 0.0


def test_precision_en_k_sin_suficientes_relatos_devuelve_cero() -> None:
    relatos = [RelatoEtiquetado("u1", "", "fenomeno_a")]
    assert precision_en_k(relatos, {"u1": np.array([1.0, 0.0])}, k=1) == 0.0


def test_precision_en_k_ignora_relatos_sin_vector() -> None:
    relatos = [
        RelatoEtiquetado("u1", "", "fenomeno_a"),
        RelatoEtiquetado("u2", "", "fenomeno_a"),
        RelatoEtiquetado("u3", "", "fenomeno_b"),
    ]
    vectores = {"u1": np.array([1.0, 0.0]), "u2": np.array([0.99, 0.01])}
    assert precision_en_k(relatos, vectores, k=1) == 1.0


def test_comparar_modelos_sobre_relatos_sinteticos_bien_separados() -> None:
    relatos = [
        RelatoEtiquetado("u1", "contrabando de cigarrillos en la frontera", "contrabando"),
        RelatoEtiquetado("u2", "contrabando de mercancías en bodegas urbanas", "contrabando"),
        RelatoEtiquetado(
            "u3", "testaferrato en la compra de inmuebles de alto valor", "testaferros"
        ),
        RelatoEtiquetado(
            "u4", "uso de terceros como testaferros para ocultar bienes", "testaferros"
        ),
    ]
    resultados = comparar_modelos(relatos, [MODELO_RAPIDO], k=1)
    assert len(resultados) == 1
    assert resultados[0].nombre_modelo == MODELO_RAPIDO
    assert resultados[0].n_relatos == 4
    assert resultados[0].precision_en_k >= 0.5
