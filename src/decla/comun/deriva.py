"""Deriva de datos (plan_trabajo.md Fase 12; I4, Bloque 4C): PSI y KS — la alternativa a
Evidently que el propio plan ofrece ("pruebas propias con SciPy"), para no añadir una
dependencia nueva sin un caso de uso que la justifique (CLAUDE.md §2.2, §3.1).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import ks_2samp


def psi_numerico(base: list[float], nuevo: list[float], n_bins: int = 10) -> float:
    """Population Stability Index para una variable numérica. Los bordes de los bins se fijan
    por los percentiles de la distribución **base** (no de la nueva): así el bin no se mueve con
    el propio lote que se está evaluando, que es justo lo que se quiere detectar si cambió.

    Umbrales de lectura estándar (literatura de riesgo crediticio, no inventados aquí): < 0,1
    sin cambio relevante; 0,1-0,25 cambio moderado; > 0,25 cambio significativo.
    """
    base_arr = np.array(base, dtype=float)
    nuevo_arr = np.array(nuevo, dtype=float)
    if len(base_arr) == 0 or len(nuevo_arr) == 0:
        return float("nan")

    bordes = np.unique(np.percentile(base_arr, np.linspace(0, 100, n_bins + 1)))
    if len(bordes) < 2:
        return 0.0  # base constante: no hay con qué repartir en bins, no se puede medir deriva
    bordes[0], bordes[-1] = -np.inf, np.inf

    conteo_base, _ = np.histogram(base_arr, bins=bordes)
    conteo_nuevo, _ = np.histogram(nuevo_arr, bins=bordes)
    pct_base = np.clip(conteo_base / len(base_arr), 1e-6, None)
    pct_nuevo = np.clip(conteo_nuevo / len(nuevo_arr), 1e-6, None)
    return float(np.sum((pct_nuevo - pct_base) * np.log(pct_nuevo / pct_base)))


def psi_categorico(conteos_base: dict[str, int], conteos_nuevo: dict[str, int]) -> float:
    """Igual que `psi_numerico`, pero para una variable categórica (p. ej. distribución de
    delito o de departamento) — las categorías son las que ya existen, no bins calculados.
    """
    total_base = sum(conteos_base.values())
    total_nuevo = sum(conteos_nuevo.values())
    if total_base == 0 or total_nuevo == 0:
        return float("nan")

    categorias = set(conteos_base) | set(conteos_nuevo)
    psi_total = 0.0
    for categoria in categorias:
        pct_base = max(conteos_base.get(categoria, 0) / total_base, 1e-6)
        pct_nuevo = max(conteos_nuevo.get(categoria, 0) / total_nuevo, 1e-6)
        psi_total += (pct_nuevo - pct_base) * np.log(pct_nuevo / pct_base)
    return float(psi_total)


def ks_dos_muestras(base: list[float], nuevo: list[float]) -> dict[str, Any]:
    """Wrapper documentado de `scipy.stats.ks_2samp`: p bajo = las dos muestras probablemente
    no vienen de la misma distribución."""
    if len(base) == 0 or len(nuevo) == 0:
        return {"estadistico": None, "p": None}
    resultado = ks_2samp(base, nuevo)
    return {
        "estadistico": round(float(resultado.statistic), 4),
        "p": round(float(resultado.pvalue), 4),
    }
