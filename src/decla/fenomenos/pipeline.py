"""Punto de entrada de `make fenomenos`: descubrimiento de fenómenos (Fase 6, Bloque 2C).

Lee `data/warehouse.duckdb` en lectura-escritura (deben existir ya `make etl`, `make nlp` y
`make conocimiento`) y escribe `fenomenos.grupos_descubiertos` ahí, más
`config/taxonomia/v0.1-borrador.yaml`. Nunca toca `data/raw/` directamente.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.fenomenos.orquestador import (
    RUTA_EMBEDDINGS_DEFECTO,
    ResumenFenomenos,
    procesar_fenomenos,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def ejecutar_fenomenos(
    ruta_duckdb: Path,
    lote_id: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DEFECTO,
) -> tuple[str, ResumenFenomenos]:
    run_id = str(uuid.uuid4())
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(conexion, paso="fenomenos", parametros={"lote_id": lote_id}):
            resumen = procesar_fenomenos(conexion, lote_id, run_id, ruta_embeddings_datos)
    finally:
        conexion.close()
    return run_id, resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", required=True, help="lote_id usado en `make nlp`.")
    parser.add_argument("--embeddings", type=Path, default=RUTA_EMBEDDINGS_DEFECTO)
    args: Any = parser.parse_args(argv)

    run_id, resumen = ejecutar_fenomenos(args.duckdb, args.lote_id, args.embeddings)

    print(f"Fenómenos completo — run_id={run_id}")
    print(f"  {resumen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
