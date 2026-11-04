"""Novedad combinatoria y semántica (plan_trabajo.md §8.5, Fase 8).

**Novedad semántica reducida de alcance a propósito**: "relatos lejanos a todos los centroides
que forman grupo nuevo denso" exigiría volver a correr UMAP+HDBSCAN (Fase 6) sobre los relatos no
clasificados — es la misma maquinaria de `decla.fenomenos.orquestador`, no código nuevo de este
bloque. Ese paso queda como **procedimiento**: recortar `fenomenos.asignacion_fenomeno` por
"no_clasificado" y volver a correr `make fenomenos` sobre ese subconjunto, documentado en
`docs/manual_app.md`, no reimplementado aquí. Lo que sí se construye: divergencia de vocabulario
(Jensen-Shannon) y deriva de centroide entre dos ventanas de tiempo — ambas funciones puras,
reciben los vectores/frecuencias ya calculados, no vuelven a tocar la base de datos.
"""

from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import polars as pl
from scipy.spatial.distance import jensenshannon


def novedad_combinatoria(
    conexion: duckdb.DuckDBPyConnection,
    indice_periodo_corte: int,
    columna_territorio: str = "cod_dpto_hechos",
    soporte_minimo: int = 1,
) -> pl.DataFrame:
    """Combinaciones (fenómeno, sector, territorio) presentes en el periodo "reciente"
    (`indice_periodo >= indice_periodo_corte`) que no aparecían en el periodo "base" (anterior),
    con soporte mínimo en el periodo reciente (plan §8.5: "se exige soporte mínimo").
    """
    base = conexion.sql(
        f"""
        SELECT a.codigo_fenomeno,
               coalesce(m.valor_normalizado, 'sin_sector') AS sector,
               r.{columna_territorio} AS territorio,
               r.anio_iso_creacion * 12 + r.mes_creacion AS indice_periodo
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        LEFT JOIN texto.menciones m
          ON m.registro_uid = a.registro_uid AND m.categoria = 'sector' AND m.polaridad = 'afirmada'
        WHERE r.{columna_territorio} IS NOT NULL AND r.fecha_creacion_valida
        """
    ).pl()
    if base.height == 0:
        return pl.DataFrame()

    columnas_combo = ["codigo_fenomeno", "sector", "territorio"]
    reciente = base.filter(pl.col("indice_periodo") >= indice_periodo_corte)
    anterior = base.filter(pl.col("indice_periodo") < indice_periodo_corte)

    combos_reciente = (
        reciente.group_by(columnas_combo).agg(pl.len().alias("n_reciente"))
        .filter(pl.col("n_reciente") >= soporte_minimo)
    )
    combos_base = (
        anterior.select(columnas_combo).unique().with_columns(pl.lit(True).alias("ya_existia"))
    )

    return (
        combos_reciente.join(combos_base, on=columnas_combo, how="left")
        .filter(pl.col("ya_existia").is_null())
        .drop("ya_existia")
        .sort("n_reciente", descending=True)
    )


def divergencia_js_vocabulario(
    frecuencias_base: dict[str, int], frecuencias_reciente: dict[str, int]
) -> float:
    """Divergencia de Jensen-Shannon (0 = idéntico, 1 = disjunto en base 2) entre dos
    distribuciones de vocabulario, alineando el vocabulario de ambas ventanas."""
    vocabulario = sorted(set(frecuencias_base) | set(frecuencias_reciente))
    if not vocabulario:
        return 0.0
    p = np.array([frecuencias_base.get(t, 0) for t in vocabulario], dtype=float)
    q = np.array([frecuencias_reciente.get(t, 0) for t in vocabulario], dtype=float)
    if p.sum() == 0 or q.sum() == 0:
        return float("nan")
    return float(jensenshannon(p / p.sum(), q / q.sum(), base=2))


def deriva_centroide(centroide_base: np.ndarray, centroide_reciente: np.ndarray) -> float:
    """Distancia coseno entre el centroide de un fenómeno en dos ventanas de tiempo (0 = sin
    deriva, 1 = ortogonal). Un valor alto puede indicar un nuevo modus operandi o un error de
    clasificación (plan §7.5) — se reporta, no se interpreta automáticamente.
    """
    norma_base = np.linalg.norm(centroide_base)
    norma_reciente = np.linalg.norm(centroide_reciente)
    if norma_base == 0 or norma_reciente == 0:
        return float("nan")
    coseno = float(np.dot(centroide_base, centroide_reciente) / (norma_base * norma_reciente))
    return round(1 - coseno, 6)


def resumen_novedad(
    combinatoria: pl.DataFrame, divergencia_vocabulario: float, deriva: float
) -> dict[str, Any]:
    return {
        "n_combinaciones_nuevas": combinatoria.height,
        "combinaciones_nuevas": combinatoria,
        "divergencia_js_vocabulario": divergencia_vocabulario,
        "deriva_centroide": deriva,
    }
