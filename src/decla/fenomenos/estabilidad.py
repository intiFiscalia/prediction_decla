"""Estabilidad de agrupamiento (plan_trabajo.md §7.1 paso 3; Fase 6, Bloque 2C).

Mide si un agrupamiento es una estructura real o un accidente de la semilla o la submuestra:
ARI/NMI entre corridas con distinta semilla y submuestra (bootstrap), y % de ruido (HDBSCAN).
Sobre fixtures, también mide la recuperación del `fenomeno_plantado`
(`tests/fixtures/verdad.parquet`) — un criterio de referencia para el desarrollo, no la compuerta
dura de aprobación de la taxonomía (eso lo decide el taller con analistas, plan_trabajo.md §7.2).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

from decla.fenomenos.agrupamiento import RUIDO, ResultadoAgrupamiento


@dataclass(frozen=True)
class ResumenEstabilidad:
    ari_promedio: float
    nmi_promedio: float
    n_corridas: int
    pct_ruido_promedio: float


def porcentaje_ruido(etiquetas: np.ndarray, valor_ruido: int = RUIDO) -> float:
    if len(etiquetas) == 0:
        return 0.0
    return float(np.mean(etiquetas == valor_ruido))


def comparar_particiones(
    etiquetas_a: np.ndarray, etiquetas_b: np.ndarray
) -> tuple[float, float]:
    return (
        float(adjusted_rand_score(etiquetas_a, etiquetas_b)),
        float(adjusted_mutual_info_score(etiquetas_a, etiquetas_b)),
    )


def evaluar_estabilidad_bootstrap(
    matriz: np.ndarray,
    funcion_agrupar: Callable[[np.ndarray, int], ResultadoAgrupamiento],
    n_corridas: int,
    fraccion_submuestra: float,
    semilla_base: int,
) -> ResumenEstabilidad:
    """Agrupa `n_corridas` veces sobre submuestras aleatorias (bootstrap, semillas distintas) y
    compara cada corrida contra la siguiente en los índices que ambas submuestras comparten.
    """
    rng = np.random.default_rng(semilla_base)
    n = matriz.shape[0]
    tamano_submuestra = max(2, int(n * fraccion_submuestra))

    corridas: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(n_corridas):
        indices = rng.choice(n, size=tamano_submuestra, replace=False)
        resultado = funcion_agrupar(matriz[indices], semilla_base + i)
        corridas.append((indices, resultado.etiquetas))

    pcts_ruido = [porcentaje_ruido(etiquetas) for _, etiquetas in corridas]

    aris: list[float] = []
    nmis: list[float] = []
    for (indices_a, etiquetas_a), (indices_b, etiquetas_b) in zip(
        corridas[:-1], corridas[1:], strict=False
    ):
        comunes = np.intersect1d(indices_a, indices_b)
        if len(comunes) < 2:
            continue
        mapa_a = dict(zip(indices_a.tolist(), etiquetas_a.tolist(), strict=True))
        mapa_b = dict(zip(indices_b.tolist(), etiquetas_b.tolist(), strict=True))
        sub_a = np.array([mapa_a[idx] for idx in comunes])
        sub_b = np.array([mapa_b[idx] for idx in comunes])
        ari, nmi = comparar_particiones(sub_a, sub_b)
        aris.append(ari)
        nmis.append(nmi)

    return ResumenEstabilidad(
        ari_promedio=round(float(np.mean(aris)), 4) if aris else 0.0,
        nmi_promedio=round(float(np.mean(nmis)), 4) if nmis else 0.0,
        n_corridas=n_corridas,
        pct_ruido_promedio=round(float(np.mean(pcts_ruido)), 4),
    )


def precision_recuperacion_fenomeno(
    etiquetas_predichas: np.ndarray, fenomenos_plantados: list[str]
) -> float:
    """Para cada grupo predicho (sin contar ruido), la proporción del fenómeno plantado
    mayoritario dentro de ese grupo, ponderada por tamaño de grupo: mide si el agrupamiento
    recupera los fenómenos plantados en fixtures, no se usa sobre datos reales (no hay verdad de
    terreno real).
    """
    etiquetas_arreglo = np.asarray(etiquetas_predichas)
    n_total_sin_ruido = 0
    n_correctos = 0
    for etiqueta in sorted(set(etiquetas_arreglo.tolist())):
        if etiqueta == RUIDO:
            continue
        indices = np.where(etiquetas_arreglo == etiqueta)[0]
        fenomenos_del_grupo = [fenomenos_plantados[i] for i in indices]
        _, conteo = Counter(fenomenos_del_grupo).most_common(1)[0]
        n_total_sin_ruido += len(indices)
        n_correctos += conteo
    return round(n_correctos / n_total_sin_ruido, 4) if n_total_sin_ruido else 0.0
