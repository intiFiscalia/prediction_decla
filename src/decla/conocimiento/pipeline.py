"""Punto de entrada de `make conocimiento`: extracción de menciones con evidencia (Fase 5,
Bloque 2B).

Lee `data/warehouse.duckdb` en lectura-escritura (debe existir ya, vía `make etl` + `make nlp`) y
escribe `texto.menciones` ahí. Nunca toca `data/raw/` directamente: todo lo que necesita ya está
en `texto.relato_procesado`.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.conocimiento.orquestador import ResumenConocimiento, procesar_conocimiento

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def ejecutar_conocimiento(ruta_duckdb: Path) -> tuple[str, ResumenConocimiento]:
    run_id = str(uuid.uuid4())
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(conexion, paso="conocimiento"):
            resumen = procesar_conocimiento(conexion, run_id)
    finally:
        conexion.close()
    return run_id, resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    args: Any = parser.parse_args(argv)

    run_id, resumen = ejecutar_conocimiento(args.duckdb)

    print(f"Conocimiento completo — run_id={run_id}")
    print(f"  {resumen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
