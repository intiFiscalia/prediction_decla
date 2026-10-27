"""Calcula el resumen de pares calificados sin pasar por la interfaz Streamlit (más rápido para
iterar entre modelos). Uso:

    uv run python scripts/resumen_pares_calificados.py --lote-id <uuid>
    uv run python scripts/resumen_pares_calificados.py --lote-id <uuid> --umbral 0.6
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from decla.texto.herramienta_anotacion_pares import (
    RUTA_CALIFICACIONES_DEFECTO,
    RUTA_RESUMEN_DEFECTO,
    calcular_acuerdo,
    cargar_calificaciones,
    escribir_resumen,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_EMBEDDINGS = RAIZ_PROYECTO / "data" / "embeddings"


def cargar_vectores(lote_id: str) -> dict[str, list[float]]:
    ruta = RUTA_EMBEDDINGS / lote_id / "relato.parquet"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}; corre `make nlp` con ese lote_id primero.")
    df = pl.read_parquet(ruta).filter(pl.col("agregacion") == "media")
    return dict(zip(df["registro_uid"].to_list(), df["vector"].to_list(), strict=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lote-id", required=True)
    parser.add_argument("--umbral", type=float, default=0.5)
    parser.add_argument("--salida", type=Path, default=RUTA_RESUMEN_DEFECTO)
    args = parser.parse_args(argv)

    calificaciones = cargar_calificaciones(RUTA_CALIFICACIONES_DEFECTO)
    vectores = cargar_vectores(args.lote_id)
    resumen = calcular_acuerdo(calificaciones, vectores, umbral_similitud=args.umbral)
    escribir_resumen(resumen, args.salida)

    print(resumen)
    print(f"Resumen escrito en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
