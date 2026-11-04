"""Detectores de exceso sobre la línea base (plan_trabajo.md §8.5, Fase 8): CUSUM, EARS,
Farrington simplificado, puntos de cambio y razón de tasas. Todos trabajan sobre los residuos o
conteos que produce `decla.emergencia.linea_base.ajustar_linea_base` — ninguno vuelve a tocar la
base de datos.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import poisson

# --- p-valor de exceso de la ventana reciente vs. periodos base ------------------------------


def p_valor_exceso_ventana_reciente(
    observados: list[float], volumenes: list[float], ancho_ventana: int
) -> float:
    """p-valor (Poisson, un lado) de que la **ventana reciente completa** (los últimos
    `ancho_ventana` periodos, el tamaño de la persistencia mínima exigida) exceda la tasa de los
    periodos base (todos los anteriores).

    Es el "p formal" que usa `decla.emergencia.orquestador` para la corrección de Benjamini-
    Hochberg. No se usa un solo punto fuera de muestra (como un ajuste de tendencia con el último
    periodo excluido) porque con series cortas (~6-10 periodos) dos o más periodos anómalos
    consecutivos se "explican" entre sí en ese ajuste: el periodo evaluado nunca queda realmente
    fuera de la influencia del anterior si éste también es parte del pico. Comparar la ventana
    reciente agregada contra la tasa de los periodos base evita ese enmascaramiento — es la misma
    lógica de `razon_de_tasas`, aplicada aquí como prueba formal de significancia.
    """
    if len(observados) <= ancho_ventana:
        return 1.0  # no hay periodos base fuera de la ventana reciente: no se puede comparar

    n_reciente = sum(observados[-ancho_ventana:])
    volumen_reciente = sum(volumenes[-ancho_ventana:])
    n_base = sum(observados[:-ancho_ventana])
    volumen_base = sum(volumenes[:-ancho_ventana])
    if volumen_base == 0:
        return 1.0

    tasa_base = n_base / volumen_base
    esperado_reciente = tasa_base * volumen_reciente
    return float(poisson.sf(max(n_reciente - 1, 0), max(esperado_reciente, 1e-6)))


# --- CUSUM sobre residuos estandarizados -----------------------------------------------------


def cusum(residuos: list[float], k: float = 0.5, h: float = 4.0) -> dict[str, Any]:
    """CUSUM de una cola (detecta aumentos) sobre residuos de Pearson ya estandarizados.
    `k` (holgura, en desviaciones) y `h` (umbral de decisión) son los valores de referencia
    estándar de control de procesos (Montgomery, *Introduction to Statistical Quality Control*),
    no un ajuste oculto — se exponen como parámetros.
    """
    c = 0.0
    trayectoria = []
    periodo_alerta = None
    for i, r in enumerate(residuos):
        c = max(0.0, c + r - k)
        trayectoria.append(c)
        if c > h and periodo_alerta is None:
            periodo_alerta = i
    return {
        "trayectoria": trayectoria,
        "umbral": h,
        "periodo_alerta": periodo_alerta,
        "en_alerta": periodo_alerta is not None,
    }


# --- EARS (adaptado a periodicidad mensual, no diaria) ---------------------------------------


def ears_c(conteos: list[float], ventana_base: int = 3) -> dict[str, Any]:
    """EARS compara el periodo actual contra la media/desviación de una ventana base reciente
    (plan §8.5). El EARS original usa ventanas de 7 días (vigilancia diaria); aquí la serie es
    mensual, así que `ventana_base` son **meses** anteriores, no días — adaptación explícita, no
    el mismo EARS C1-C3 de la literatura de vigilancia diaria.
    """
    if len(conteos) <= ventana_base:
        return {"calculado": False, "motivo": f"se necesitan > {ventana_base} periodos"}

    base = np.array(conteos[-ventana_base - 1 : -1], dtype=float)
    actual = float(conteos[-1])
    media_base, sd_base = float(base.mean()), float(base.std(ddof=1)) if ventana_base > 1 else 0.0
    c_estadistico = (actual - media_base) / sd_base if sd_base > 0 else None
    return {
        "calculado": True,
        "c_estadistico": round(c_estadistico, 4) if c_estadistico is not None else None,
        "media_base": round(media_base, 4),
        "sd_base": round(sd_base, 4),
        "actual": actual,
        "en_alerta": c_estadistico is not None and c_estadistico > 3,  # EARS C1: umbral C > 3
    }


# --- Farrington flexible, versión simplificada y documentada ---------------------------------


def farrington_simplificado(
    n_esperado: list[float], n_observado: list[float], umbral_desviaciones: float = 2.58
) -> dict[str, Any]:
    """Versión simplificada de Farrington flexible: reponderación de un solo paso (los periodos
    con residuo de Anscombe > 1.0 se excluyen al recalcular la media/varianza esperadas, como
    aproximación al reponderamiento iterativo del método original) y umbral normal sobre la
    varianza de Poisson, no la transformación de potencia 2/3 completa del paper original.

    **Esto no es `surveillance::farringtonFlexible` (R).** Con <1 año de historia no hay base
    multianual para la que Farrington fue diseñado (comparar el mismo mes en años previos); se
    construye y mide igual, pero el resultado siempre debe leerse con esa advertencia.
    """
    if len(n_esperado) < 3:
        return {"calculado": False, "motivo": "se necesitan ≥3 periodos"}

    esperado = np.array(n_esperado, dtype=float)
    observado = np.array(n_observado, dtype=float)
    anscombe = 1.5 * (np.cbrt(observado) - np.cbrt(esperado)) / np.cbrt(np.maximum(esperado, 1e-6))

    conservar = np.abs(anscombe[:-1]) <= 1.0  # excluye outliers de los periodos *previos* al actual
    base_reponderada = esperado[:-1][conservar]
    if len(base_reponderada) < 2:
        media, varianza = float(esperado[:-1].mean()), float(esperado[:-1].var(ddof=1))
    else:
        media, varianza = float(base_reponderada.mean()), float(base_reponderada.var(ddof=1))
    varianza = max(varianza, media)  # nunca por debajo del caso Poisson puro

    umbral = media + umbral_desviaciones * (varianza**0.5)
    actual = float(observado[-1])
    return {
        "calculado": True,
        "media_base_reponderada": round(media, 4),
        "umbral": round(umbral, 4),
        "actual": actual,
        "en_alerta": actual > umbral,
        "n_periodos_excluidos_de_base": int((~conservar).sum()),
    }


# --- Puntos de cambio (ruptures) --------------------------------------------------------------


def puntos_de_cambio(conteos: list[float], penalidad: float = 3.0) -> list[int]:
    """PELT (`ruptures`) con modelo L2 y penalidad explícita (no un número de puntos fijado de
    antemano: con una serie de ~10 periodos, fijar k de puntos sería adivinar).
    """
    import ruptures as rpt

    if len(conteos) < 4:
        return []
    algoritmo = rpt.Pelt(model="l2", min_size=2).fit(np.array(conteos, dtype=float))
    puntos = algoritmo.predict(pen=penalidad)
    return [p for p in puntos if p < len(conteos)]  # ruptures incluye len(serie) como cierre


# --- Razón de tasas reciente vs. base ---------------------------------------------------------


def razon_de_tasas(
    n_reciente: int, periodos_reciente: int, n_base: int, periodos_base: int
) -> dict[str, Any]:
    """Razón de tasas (conteo/periodo) reciente vs. base, con IC 95% exacto de Poisson (método
    de razón de verosimilitud vía percentiles de Poisson, sin asumir normalidad con conteos
    bajos).
    """
    if periodos_reciente == 0 or periodos_base == 0 or n_base == 0:
        return {"calculado": False, "motivo": "periodos o conteo base en cero"}

    tasa_reciente = n_reciente / periodos_reciente
    tasa_base = n_base / periodos_base
    razon = tasa_reciente / tasa_base if tasa_base > 0 else None

    # IC 95% aproximado por simulación de la razón de dos tasas de Poisson (percentiles 2.5/97.5).
    rng = np.random.default_rng(20260101)
    sim_reciente_n = poisson.rvs(mu=max(n_reciente, 0.5), size=5000, random_state=rng)
    sim_reciente = sim_reciente_n / periodos_reciente
    sim_base = poisson.rvs(mu=max(n_base, 0.5), size=5000, random_state=rng) / periodos_base
    sim_razon = sim_reciente / np.where(sim_base == 0, np.nan, sim_base)
    ic_bajo, ic_alto = np.nanpercentile(sim_razon, [2.5, 97.5])

    return {
        "calculado": True,
        "tasa_reciente": round(tasa_reciente, 4),
        "tasa_base": round(tasa_base, 4),
        "razon_de_tasas": round(razon, 4) if razon is not None else None,
        "ic_95": (round(float(ic_bajo), 4), round(float(ic_alto), 4)),
    }
