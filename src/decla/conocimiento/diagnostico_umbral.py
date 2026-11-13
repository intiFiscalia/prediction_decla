"""Diagnóstico de la distribución real de `confianza` del clasificador zero-shot
(`decla.conocimiento.zero_shot`), para recalibrar `config/umbrales.yaml` con evidencia del
corpus real en vez de con las 4 oraciones sintéticas usadas en la calibración inicial (ver
comentario en `config/umbrales.yaml` y ADR 0010: el mismo patrón ya le pasó a `sector_inferido`,
que terminó en 95 % `indeterminado` sobre datos reales).

`texto.menciones` guarda `confianza` (la similitud top-1 real) **incluso cuando el resultado
quedó `no_clasificado`** (`decla.conocimiento.zero_shot.elegir_por_similitud`) — no hay que
recalcular nada, solo agregar lo que ya existe. Solo se agregan estadísticos (percentiles,
conteos por umbral candidato); nunca se expone texto ni `registro_uid` individual (CLAUDE.md
§2.1).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import polars as pl

from decla.comun.duckdb_io import conectar
from decla.comun.supresion import suprimir_celdas_bajas

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_SALIDA_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "diagnostico"

PERCENTILES = [0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
UMBRALES_CANDIDATOS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]


def percentiles_confianza(conexion: duckdb.DuckDBPyConnection, categoria: str) -> pl.DataFrame:
    """Un resumen (una fila) de la columna `confianza` de `texto.menciones` para `categoria`,
    restringido a `origen='inferido_modelo'` (el único camino con un umbral que ajustar; el
    explícito siempre vale 1.0 y no aporta a la calibración).
    """
    confianzas = conexion.sql(
        "SELECT confianza FROM texto.menciones WHERE categoria = ? AND origen = 'inferido_modelo'",
        params=[categoria],
    ).pl()["confianza"]

    if confianzas.is_empty():
        return pl.DataFrame([{"categoria": categoria, "n_inferido": 0}])

    fila: dict[str, float | int | str] = {"categoria": categoria, "n_inferido": confianzas.len()}
    for p in PERCENTILES:
        fila[f"p{int(p * 100)}"] = round(float(confianzas.quantile(p)), 4)
    return pl.DataFrame([fila])


def sensibilidad_umbral(
    conexion: duckdb.DuckDBPyConnection, categoria: str, umbrales: list[float] = UMBRALES_CANDIDATOS
) -> pl.DataFrame:
    """Para cada umbral candidato de `confianza_minima`, cuántas menciones inferidas de
    `categoria` dejarían de quedar `no_clasificado` si ese fuera el umbral — sin recalcular el
    margen top1-top2 (no se guarda por mención), así que es una cota optimista: el conteo real
    tras recalibrar sería igual o menor.
    """
    confianzas = conexion.sql(
        "SELECT confianza FROM texto.menciones WHERE categoria = ? AND origen = 'inferido_modelo'",
        params=[categoria],
    ).pl()["confianza"]
    n_total = confianzas.len()

    filas = [
        {
            "categoria": categoria,
            "umbral_candidato": umbral,
            "n_pasaria": int((confianzas >= umbral).sum()),
            "n_total_inferido": n_total,
        }
        for umbral in umbrales
    ]
    df = pl.DataFrame(filas)
    if df.height == 0:
        return df
    df = df.with_columns(
        (pl.col("n_pasaria") * 100.0 / pl.col("n_total_inferido")).round(2).alias("pct_pasaria")
    )
    return suprimir_celdas_bajas(df, ["n_pasaria"])


def construir_diagnostico_umbral(
    conexion: duckdb.DuckDBPyConnection, categorias: list[str] = ("sector", "mecanismo")  # type: ignore[assignment]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    percentiles = pl.concat(
        [percentiles_confianza(conexion, c) for c in categorias], how="diagonal_relaxed"
    )
    sensibilidad = pl.concat(
        [sensibilidad_umbral(conexion, c) for c in categorias], how="diagonal_relaxed"
    )
    return percentiles, sensibilidad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_SALIDA_DEFECTO)
    args = parser.parse_args(argv)

    conexion = conectar(args.duckdb, solo_lectura=True)
    try:
        percentiles, sensibilidad = construir_diagnostico_umbral(conexion)
    finally:
        conexion.close()

    args.salida.mkdir(parents=True, exist_ok=True)
    percentiles.write_csv(args.salida / "umbral_zero_shot_percentiles.csv")
    sensibilidad.write_csv(args.salida / "umbral_zero_shot_sensibilidad.csv")
    print(percentiles)
    print(sensibilidad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
