"""Pronósticos de frecuencia por fenómeno (plan_trabajo.md §8.4, Fase 9; ADR 0016).

Reabierto tras ADR 0016: el umbral de ≥36 meses que bloqueaba esta pieza lo fijó la planeación
inicial sin conocer que los datos llegan por entregas anuales. Se construye con la historia
disponible, con garantías no negociables (ADR 0016):

1. **Modelo ingenuo obligatorio** (`pronostico_ingenuo`) — todo método más complejo se reporta
   junto a él, nunca solo.
2. **Sin estacionalidad con menos de 12 meses de historia** — ni el ingenuo es "estacional"
   (sería el mismo mes del año anterior, que no existe todavía), ni ETS/Poisson llevan término
   estacional. Solo tendencia, igual que `decla.emergencia.linea_base` (I3).
3. **Intervalos de confianza explícitamente anchos** — se calculan y se reportan completos
   (80 % y 95 %), nunca se recorta ni se oculta su amplitud real.
4. ***Rolling origin* con tantos orígenes como la historia permita** (`evaluar_rolling_origin`)
   — reporta `n_origenes`, nunca simula orígenes que no existen.

No usa StatsForecast/HierarchicalForecast (no son dependencias aprobadas, CLAUDE.md §2.2/§3.1) —
`statsmodels` (ya dependencia, ya usado en `linea_base.py`) basta para el volumen de series real
(decenas, no miles).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import nbinom, poisson

MINIMO_PERIODOS_ENTRENAMIENTO = 4  # mismo mínimo que decla.emergencia.linea_base.ajustar_linea_base


@dataclass(frozen=True)
class ResultadoPronostico:
    calculado: bool
    metodo: str
    motivo: str | None = None
    valores_punto: list[float] | None = None
    intervalo_80: list[tuple[float, float]] | None = None
    intervalo_95: list[tuple[float, float]] | None = None


def pronostico_ingenuo(serie_n: list[float], horizonte: int) -> ResultadoPronostico:
    """Último valor observado, repetido `horizonte` veces. No es un "ingenuo estacional" (eso
    exigiría el mismo mes del año anterior, que no existe con menos de 12 meses de historia,
    ADR 0016) — es el ingenuo de referencia obligatorio con el que se compara todo lo demás.
    """
    if not serie_n:
        return ResultadoPronostico(False, "ingenuo", motivo="serie vacía")
    ultimo = float(serie_n[-1])
    return ResultadoPronostico(
        calculado=True,
        metodo="ingenuo",
        valores_punto=[ultimo] * horizonte,
        intervalo_80=None,
        intervalo_95=None,
    )


def pronostico_ets_tendencia(
    serie_n: list[float], horizonte: int, semilla: int = 20260101, repeticiones: int = 500
) -> ResultadoPronostico:
    """Holt (tendencia aditiva, **sin estacionalidad** — ADR 0016). Intervalos por simulación de
    innovaciones (`ExponentialSmoothing.simulate`), no por una fórmula gaussiana cerrada: con
    tan pocos periodos, la distribución de los residuos no se puede asumir normal de antemano.
    """
    if len(serie_n) < MINIMO_PERIODOS_ENTRENAMIENTO:
        return ResultadoPronostico(
            False, "ets_tendencia", motivo=f"menos de {MINIMO_PERIODOS_ENTRENAMIENTO} periodos"
        )

    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    y = np.array(serie_n, dtype=float)
    try:
        modelo = ExponentialSmoothing(
            y, trend="add", seasonal=None, initialization_method="estimated"
        ).fit()
    except Exception as error:  # ver nota de red de seguridad en linea_base.py — mismo motivo
        return ResultadoPronostico(False, "ets_tendencia", motivo=f"ajuste no estable: {error}")

    puntos = modelo.forecast(horizonte)
    simulaciones = modelo.simulate(
        horizonte, repetitions=repeticiones, rng=np.random.default_rng(semilla)
    )
    intervalo_80 = list(
        zip(
            np.percentile(simulaciones, 10, axis=1).tolist(),
            np.percentile(simulaciones, 90, axis=1).tolist(),
            strict=True,
        )
    )
    intervalo_95 = list(
        zip(
            np.percentile(simulaciones, 2.5, axis=1).tolist(),
            np.percentile(simulaciones, 97.5, axis=1).tolist(),
            strict=True,
        )
    )
    return ResultadoPronostico(
        calculado=True,
        metodo="ets_tendencia",
        valores_punto=puntos.tolist(),
        intervalo_80=intervalo_80,
        intervalo_95=intervalo_95,
    )


def pronostico_poisson_nb_tendencia(
    serie_n: list[float], volumenes: list[float], horizonte: int
) -> ResultadoPronostico:
    """GLM Poisson con tendencia y *offset* (reajusta a binomial negativa si hay sobredispersión
    — misma regla que `decla.emergencia.linea_base.ajustar_linea_base`). **Supuesto explícito y
    documentado, no oculto**: el volumen total del territorio en los periodos futuros se asume
    igual al del último periodo observado, por ausencia de información mejor — si el volumen
    real cambia, este pronóstico se degrada igual que cualquier offset mal estimado.
    """
    if len(serie_n) < MINIMO_PERIODOS_ENTRENAMIENTO:
        return ResultadoPronostico(
            False, "poisson_nb_tendencia",
            motivo=f"menos de {MINIMO_PERIODOS_ENTRENAMIENTO} periodos",
        )
    if sum(serie_n) == 0:
        return ResultadoPronostico(
            False, "poisson_nb_tendencia", motivo="sin ninguna ocurrencia en esta serie"
        )

    import statsmodels.api as sm

    indices = np.arange(len(serie_n))
    x = sm.add_constant(indices)
    offset = np.log(np.clip(np.array(volumenes, dtype=float), 1, None))

    try:
        modelo = sm.GLM(serie_n, x, family=sm.families.Poisson(), offset=offset).fit()
        residuos = modelo.resid_pearson
        sobredispersion = (
            float((residuos**2).sum() / modelo.df_resid) if modelo.df_resid > 0 else 0.0
        )
        metodo_familia: Literal["poisson", "binomial_negativa"] = "poisson"
        if sobredispersion > 1.5:
            modelo = sm.GLM(serie_n, x, family=sm.families.NegativeBinomial(), offset=offset).fit()
            metodo_familia = "binomial_negativa"
    except Exception as error:
        return ResultadoPronostico(
            False, "poisson_nb_tendencia", motivo=f"ajuste no estable: {error}"
        )

    indices_futuros = np.arange(len(serie_n), len(serie_n) + horizonte)
    x_futuro = sm.add_constant(indices_futuros, has_constant="add")
    offset_futuro = np.full(horizonte, offset[-1])  # último volumen observado, supuesto explícito
    mu = modelo.predict(x_futuro, offset=offset_futuro)

    if metodo_familia == "binomial_negativa":
        alpha = 1.0  # mismo valor fijo que sm.families.NegativeBinomial() por defecto
        n_param = 1 / alpha
        p_param = n_param / (n_param + mu)
        intervalo_80 = list(
            zip(nbinom.ppf(0.10, n_param, p_param), nbinom.ppf(0.90, n_param, p_param), strict=True)
        )
        intervalo_95 = list(
            zip(
                nbinom.ppf(0.025, n_param, p_param),
                nbinom.ppf(0.975, n_param, p_param),
                strict=True,
            )
        )
    else:
        intervalo_80 = list(zip(poisson.ppf(0.10, mu), poisson.ppf(0.90, mu), strict=True))
        intervalo_95 = list(zip(poisson.ppf(0.025, mu), poisson.ppf(0.975, mu), strict=True))

    return ResultadoPronostico(
        calculado=True,
        metodo=f"poisson_nb_tendencia_{metodo_familia}",
        valores_punto=mu.tolist(),
        intervalo_80=[(float(a), float(b)) for a, b in intervalo_80],
        intervalo_95=[(float(a), float(b)) for a, b in intervalo_95],
    )


def _mase(errores_absolutos: list[float], escala_ingenuo: float) -> float | None:
    if escala_ingenuo == 0 or not errores_absolutos:
        return None
    return float(np.mean(errores_absolutos) / escala_ingenuo)


def evaluar_rolling_origin(
    serie_n: list[float],
    volumenes: list[float],
    nombre_metodo: str,
    horizonte: int = 1,
) -> dict[str, object]:
    """*Rolling origin*: para cada corte posible que deje ≥`MINIMO_PERIODOS_ENTRENAMIENTO`
    periodos de entrenamiento y `horizonte` periodos reales después para comparar, pronostica y
    mide el error frente al ingenuo (MASE) y frente a la escala del dato (WAPE). Con series de
    ~10 periodos esto da pocos orígenes — se reporta `n_origenes`, nunca se inventan más.
    """
    n = len(serie_n)
    origenes = list(range(MINIMO_PERIODOS_ENTRENAMIENTO, n - horizonte + 1))
    if not origenes:
        return {
            "calculado": False,
            "motivo": "historia insuficiente para ningún origen",
            "n_origenes": 0,
        }

    funciones_por_nombre = {
        "ingenuo": lambda s, v, h: pronostico_ingenuo(s, h),
        "ets_tendencia": lambda s, v, h: pronostico_ets_tendencia(s, h),
        "poisson_nb_tendencia": lambda s, v, h: pronostico_poisson_nb_tendencia(s, v, h),
    }
    funcion = funciones_por_nombre[nombre_metodo]

    errores_metodo: list[float] = []
    errores_ingenuo: list[float] = []
    reales_totales: list[float] = []
    for origen in origenes:
        entrenamiento_n = serie_n[:origen]
        entrenamiento_vol = volumenes[:origen]
        reales = serie_n[origen : origen + horizonte]

        resultado = funcion(entrenamiento_n, entrenamiento_vol, horizonte)
        resultado_ingenuo = pronostico_ingenuo(entrenamiento_n, horizonte)
        if not resultado.calculado or not resultado_ingenuo.calculado:
            continue

        assert resultado.valores_punto is not None
        assert resultado_ingenuo.valores_punto is not None
        pares_metodo = zip(resultado.valores_punto, reales, strict=True)
        pares_ingenuo = zip(resultado_ingenuo.valores_punto, reales, strict=True)
        errores_metodo.extend(abs(p - r) for p, r in pares_metodo)
        errores_ingenuo.extend(abs(p - r) for p, r in pares_ingenuo)
        reales_totales.extend(reales)

    if not errores_metodo:
        return {
            "calculado": False,
            "motivo": "ningún origen produjo un pronóstico",
            "n_origenes": 0,
        }

    escala_ingenuo = float(np.mean(errores_ingenuo)) if errores_ingenuo else 0.0
    mase = _mase(errores_metodo, escala_ingenuo)
    wape = (
        float(np.sum(errores_metodo) / np.sum(np.abs(reales_totales)))
        if np.sum(np.abs(reales_totales)) > 0
        else None
    )
    return {
        "calculado": True,
        "n_origenes": len(errores_metodo) // horizonte,
        "mase": round(mase, 4) if mase is not None else None,
        "wape": round(wape, 4) if wape is not None else None,
        "supera_ingenuo": mase is not None and mase < 1.0,
    }
