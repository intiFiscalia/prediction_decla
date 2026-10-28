"""Reducción de dimensión con UMAP (plan_trabajo.md §7.1 paso 2; Fase 6, Bloque 2C).

A 5-15 dimensiones para agrupar (nunca a 2: perdería demasiada estructura para HDBSCAN); 2
dimensiones solo para visualizar, nunca para agrupar. Semilla siempre explícita desde
`config/fenomenos.yaml` (CLAUDE.md §2.4): nunca hardcodeada.
"""

from __future__ import annotations

import numpy as np
from umap import UMAP


def reducir_dimension(
    matriz: np.ndarray,
    n_componentes: int,
    n_vecinos: int,
    metrica: str,
    semilla: int,
) -> np.ndarray:
    n_vecinos_efectivo = min(n_vecinos, matriz.shape[0] - 1)
    reductor = UMAP(
        n_components=n_componentes,
        n_neighbors=max(2, n_vecinos_efectivo),
        metric=metrica,
        random_state=semilla,
    )
    return np.asarray(reductor.fit_transform(matriz))
