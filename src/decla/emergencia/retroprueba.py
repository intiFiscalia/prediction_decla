"""Retroprueba con incrementos plantados (plan_trabajo.md §8.5, §9; Fase 8 y 10).

Mide tasa de falsas alarmas, sensibilidad y tiempo a detección del detector de exceso (`decla.
emergencia.detectores.p_valor_exceso_ventana_reciente`, el p formal que usa el orquestador para
la corrección de Benjamini-Hochberg) sobre series sintéticas con semilla fija — **nunca sobre
datos reales** (CLAUDE.md §2.1): la persona corre `make emergencia` sobre la historia real por
separado y compara su tasa de alertas contra esta retroprueba reproducible, no al revés.

Con solo 10 meses de historia real (I2 §4-bis), la retroprueba sobre el dataset real tendrá
pocos orígenes posibles (criterio de terminación de Fase 10, "orígenes móviles"); esta retroprueba
sintética no sustituye esa limitación, la complementa con una medición controlada donde se sabe
con certeza dónde está el incremento.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from decla.emergencia.detectores import p_valor_exceso_ventana_reciente


def _serie_sintetica(
    rng: np.random.Generator,
    n_periodos: int,
    tasa_base: float,
    volumen_base: float,
    periodo_incremento: int | None,
    factor_incremento: float,
) -> tuple[list[float], list[float]]:
    volumenes = np.full(n_periodos, volumen_base, dtype=float)
    tasas = np.full(n_periodos, tasa_base, dtype=float)
    if periodo_incremento is not None:
        tasas[periodo_incremento:] *= factor_incremento
    observados = rng.poisson(tasas * volumenes).astype(float)
    return observados.tolist(), volumenes.tolist()


@dataclass(frozen=True)
class ResultadoRetroprueba:
    n_series_sin_incremento: int
    n_falsas_alarmas: int
    tasa_falsas_alarmas: float
    n_series_con_incremento: int
    n_detectadas: int
    sensibilidad: float
    tiempo_a_deteccion_medio: float | None


def ejecutar_retroprueba(
    n_series: int = 200,
    n_periodos: int = 10,
    tasa_base: float = 0.15,
    volumen_base: float = 20.0,
    factor_incremento: float = 3.0,
    ancho_ventana: int = 2,
    fdr_maximo: float = 0.10,
    semilla: int = 20260101,
) -> ResultadoRetroprueba:
    """`factor_incremento` multiplica la tasa a partir del periodo `n_periodos - ancho_ventana`
    (el incremento empieza justo donde arranca la ventana reciente, el caso más favorable para
    detectarlo con persistencia completa). Todos los parámetros son explícitos — ninguno queda
    hardcodeado sin poder variarse para una retroprueba distinta.
    """
    rng = np.random.default_rng(semilla)
    periodo_incremento = n_periodos - ancho_ventana

    falsas_alarmas = 0
    for _ in range(n_series):
        observados, volumenes = _serie_sintetica(
            rng, n_periodos, tasa_base, volumen_base, None, 1.0
        )
        p = p_valor_exceso_ventana_reciente(observados, volumenes, ancho_ventana)
        if p <= fdr_maximo:
            falsas_alarmas += 1

    detectadas = 0
    tiempos_a_deteccion: list[int] = []
    for _ in range(n_series):
        observados, volumenes = _serie_sintetica(
            rng, n_periodos, tasa_base, volumen_base, periodo_incremento, factor_incremento
        )
        detectado_en: int | None = None
        for corte in range(ancho_ventana + 1, n_periodos + 1):
            p = p_valor_exceso_ventana_reciente(
                observados[:corte], volumenes[:corte], ancho_ventana
            )
            if p <= fdr_maximo:
                detectado_en = corte
                break
        if detectado_en is not None:
            detectadas += 1
            tiempos_a_deteccion.append(detectado_en - periodo_incremento)

    tiempo_medio = round(float(np.mean(tiempos_a_deteccion)), 2) if tiempos_a_deteccion else None
    return ResultadoRetroprueba(
        n_series_sin_incremento=n_series,
        n_falsas_alarmas=falsas_alarmas,
        tasa_falsas_alarmas=round(falsas_alarmas / n_series, 4),
        n_series_con_incremento=n_series,
        n_detectadas=detectadas,
        sensibilidad=round(detectadas / n_series, 4),
        tiempo_a_deteccion_medio=tiempo_medio,
    )
