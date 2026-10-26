"""Punto de entrada de `make nlp`: procesamiento base de RELATO (Fase 4, Bloque 2A).

Lee `data/warehouse.duckdb` en lectura-escritura (debe existir ya, vía `make etl`) y escribe
`texto.relato_procesado`/`texto.duplicados` ahí, más los vectores de embeddings en
`data/embeddings/`. Nunca toca `data/raw/` directamente: todo lo que necesita ya está en
`entidades.relato`.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.texto.orquestador import RUTA_EMBEDDINGS_DATOS_DEFECTO, ResumenTexto, procesar_texto

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def ejecutar_nlp(
    ruta_duckdb: Path,
    lote_id: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DATOS_DEFECTO,
) -> tuple[str, ResumenTexto]:
    run_id = str(uuid.uuid4())
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(conexion, paso="nlp", parametros={"lote_id": lote_id}):
            resumen = procesar_texto(conexion, lote_id, run_id, ruta_embeddings_datos)
    finally:
        conexion.close()
    return run_id, resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", default=None, help="Por defecto, un identificador único.")
    parser.add_argument("--embeddings", type=Path, default=RUTA_EMBEDDINGS_DATOS_DEFECTO)
    args: Any = parser.parse_args(argv)

    lote_id = args.lote_id or str(uuid.uuid4())
    run_id, resumen = ejecutar_nlp(args.duckdb, lote_id, args.embeddings)

    print(f"NLP completo — lote_id={lote_id} run_id={run_id}")
    print(f"  {resumen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
