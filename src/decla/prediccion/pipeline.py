"""Punto de entrada de `make prediccion` (I4, Fase 9 — solo detección de atípicos; pronósticos y
clasificación temática no son viables con el dataset real, ver `reports/agregados/i4/
viabilidad.md` y `docs/informes/I4_cierre.md`).

Lee `data/warehouse.duckdb` en lectura-escritura (deben existir ya `make etl`, `make nlp`,
`make conocimiento`, `make fenomenos`, `scripts/congelar_taxonomia_v1.py` y `make analitica`,
que materializa `fenomenos.asignacion_fenomeno`) y escribe `oro.atipicos` ahí.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.fenomenos.orquestador import RUTA_EMBEDDINGS_DEFECTO
from decla.prediccion.orquestador import ResumenAtipicos, procesar_atipicos

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def ejecutar_prediccion(
    ruta_duckdb: Path,
    lote_id_embeddings: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DEFECTO,
) -> tuple[str, ResumenAtipicos]:
    run_id = str(uuid.uuid4())
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    parametros = {"lote_id": lote_id_embeddings}
    try:
        with RegistroEjecucion(conexion, paso="prediccion", parametros=parametros):
            resumen = procesar_atipicos(
                conexion, lote_id_embeddings, ruta_embeddings_datos, run_id
            )
    finally:
        conexion.close()
    return run_id, resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", required=True, help="lote_id usado en `make nlp`.")
    parser.add_argument("--embeddings", type=Path, default=RUTA_EMBEDDINGS_DEFECTO)
    args: Any = parser.parse_args(argv)

    run_id, resumen = ejecutar_prediccion(args.duckdb, args.lote_id, args.embeddings)

    print(f"Atípicos completo — run_id={run_id}")
    print(f"  Registros evaluados: {resumen.n_registros}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
