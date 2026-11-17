"""Clasificador multietiqueta de fenómenos sobre el relato completo (ADR 0024;
plan_trabajo.md §7.3: "regresión logística sobre embeddings como base").

Funciones puras, probadas solo con vectores y etiquetas **sintéticos**. El entrenamiento sobre
datos reales (`decla.fenomenos.pipeline_clasificador`) pasa primero por
`verificar_cobertura_minima`: mientras algún código no tenga suficientes ejemplos confirmados o
corregidos por un analista (`config/umbrales.yaml: clasificador_fenomeno.
minimo_ejemplos_por_codigo`), esta compuerta rechaza entrenar — es la aplicación en código de
CLAUDE.md §2.3 ("no entrenes modelos supervisados sin guía de anotación y etiquetas medidas"),
no solo una nota en un documento.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.multiclass import OneVsRestClassifier


class EntrenamientoBloqueado(ValueError):
    """La compuerta de cobertura mínima (CLAUDE.md §2.3) no se cumplió todavía."""


def verificar_cobertura_minima(
    cobertura_por_codigo: dict[str, int], minimo_por_codigo: int
) -> list[str]:
    """Códigos que NO alcanzan el mínimo de ejemplos confirmados/corregidos. Lista vacía = la
    compuerta pasa y se puede entrenar."""
    return sorted(
        codigo for codigo, n in cobertura_por_codigo.items() if n < minimo_por_codigo
    )


def exigir_cobertura_minima(
    cobertura_por_codigo: dict[str, int], minimo_por_codigo: int
) -> None:
    """Igual que `verificar_cobertura_minima`, pero lanza si falta algún código — lo que usa
    `pipeline_clasificador` antes de entrenar sobre datos reales."""
    faltantes = verificar_cobertura_minima(cobertura_por_codigo, minimo_por_codigo)
    if faltantes:
        raise EntrenamientoBloqueado(
            "Entrenamiento bloqueado (CLAUDE.md §2.3, ADR 0024): faltan ejemplos anotados para "
            f"{faltantes} (mínimo {minimo_por_codigo} por código). Anota más relatos con "
            "`make anotar-fenomenos` antes de reintentar."
        )


@dataclass(frozen=True)
class ModeloFenomeno:
    modelo: OneVsRestClassifier
    codigos: list[str]


def entrenar_clasificador(
    X: np.ndarray, Y: np.ndarray, codigos: list[str], semilla: int = 20260101
) -> ModeloFenomeno:
    """`Y` es una matriz binaria (n_relatos x len(codigos)); un relato puede tener más de un 1
    (multietiqueta). Regresión logística por código (plan §7.3), no afinamiento del modelo de
    embeddings en sí."""
    base = LogisticRegression(max_iter=1000, random_state=semilla)
    modelo = OneVsRestClassifier(base)
    modelo.fit(X, Y)
    return ModeloFenomeno(modelo=modelo, codigos=codigos)


def predecir_codigos(
    modelo_fenomeno: ModeloFenomeno, X: np.ndarray, confianza_minima: float
) -> list[list[str]]:
    """Por fila, los códigos con probabilidad >= `confianza_minima`; si ninguno supera el
    umbral, lista vacía (quien llama lo interpreta como `no_clasificado`, un resultado legítimo —
    plan §7.3, nunca se fuerza una etiqueta)."""
    probabilidades = modelo_fenomeno.modelo.predict_proba(X)
    resultado: list[list[str]] = []
    for fila in probabilidades:
        resultado.append(
            [
                codigo
                for codigo, proba in zip(modelo_fenomeno.codigos, fila, strict=True)
                if proba >= confianza_minima
            ]
        )
    return resultado


@dataclass(frozen=True)
class MetricasPorCodigo:
    codigo: str
    precision: float
    exhaustividad: float
    f1: float
    n_positivos_prueba: int


def evaluar_particion_temporal(
    X: np.ndarray,
    Y: np.ndarray,
    fechas: list[str],
    codigos: list[str],
    fecha_corte: str,
    semilla: int = 20260101,
) -> list[MetricasPorCodigo]:
    """Partición temporal (nunca aleatoria, CLAUDE.md §2.3): entrena con `fecha < fecha_corte`,
    evalúa con `fecha >= fecha_corte`. Devuelve precisión/exhaustividad/F1 por código — nunca una
    sola cifra global, igual criterio que el resto del proyecto (kappa y precisión siempre por
    categoría, no agregadas)."""
    es_entrenamiento = np.array([f < fecha_corte for f in fechas])
    X_entrena, Y_entrena = X[es_entrenamiento], Y[es_entrenamiento]
    X_prueba, Y_prueba = X[~es_entrenamiento], Y[~es_entrenamiento]

    modelo_fenomeno = entrenar_clasificador(X_entrena, Y_entrena, codigos, semilla)
    Y_predicha = modelo_fenomeno.modelo.predict(X_prueba)

    metricas: list[MetricasPorCodigo] = []
    for indice, codigo in enumerate(codigos):
        y_real = Y_prueba[:, indice]
        y_pred = Y_predicha[:, indice]
        metricas.append(
            MetricasPorCodigo(
                codigo=codigo,
                precision=round(float(precision_score(y_real, y_pred, zero_division=0)), 4),
                exhaustividad=round(float(recall_score(y_real, y_pred, zero_division=0)), 4),
                f1=round(float(f1_score(y_real, y_pred, zero_division=0)), 4),
                n_positivos_prueba=int(y_real.sum()),
            )
        )
    return metricas
