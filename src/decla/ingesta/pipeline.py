"""Punto de entrada de `make etl`: bronce → plata → entidades (Fase 3 completa).

Bloqueado para Claude Code en `.claude/settings.json` (`Bash(make etl*)`): solo la persona lo
ejecuta, sobre `data/raw/` real, en su propio equipo.
"""

from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.entidades.orquestador import ResumenEntidades, construir_entidades
from decla.ingesta.bronce import ResumenLote, ingerir_lote
from decla.normalizacion.orquestador import RUTA_CLAVE_HMAC, ResumenPlata, procesar_plata

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_LOTES_DEFECTO = RAIZ_PROYECTO / "data" / "raw" / "lotes"


@dataclass
class ResultadoEtl:
    lote_id: str
    run_id: str
    bronce: list[ResumenLote]
    plata: ResumenPlata
    entidades: ResumenEntidades


def ejecutar_etl(
    directorio_entrada: Path,
    directorio_lotes: Path,
    ruta_duckdb: Path,
    lote_id: str,
    ruta_clave_hmac: Path = RUTA_CLAVE_HMAC,
) -> ResultadoEtl:
    run_id = str(uuid.uuid4())
    ruta_duckdb.parent.mkdir(parents=True, exist_ok=True)
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(conexion, paso="etl", parametros={"lote_id": lote_id}):
            resumen_bronce = ingerir_lote(directorio_entrada, directorio_lotes, lote_id, conexion)
            resumen_plata = procesar_plata(
                conexion, lote_id, run_id=run_id, ruta_clave_hmac=ruta_clave_hmac
            )
            resumen_entidades = construir_entidades(conexion, lote_id)
    finally:
        conexion.close()

    return ResultadoEtl(
        lote_id=lote_id,
        run_id=run_id,
        bronce=resumen_bronce,
        plata=resumen_plata,
        entidades=resumen_entidades,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RAIZ_PROYECTO / "data" / "raw")
    parser.add_argument("--lotes", type=Path, default=RUTA_LOTES_DEFECTO)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", default=None, help="Por defecto, un identificador único.")
    parser.add_argument("--clave-hmac", type=Path, default=RUTA_CLAVE_HMAC)
    args: Any = parser.parse_args(argv)

    lote_id = args.lote_id or str(uuid.uuid4())
    resultado = ejecutar_etl(args.entrada, args.lotes, args.duckdb, lote_id, args.clave_hmac)

    print(f"ETL completo — lote_id={resultado.lote_id} run_id={resultado.run_id}")
    print(f"  bronce: {resultado.bronce}")
    print(f"  plata: {resultado.plata}")
    print(f"  entidades: {resultado.entidades}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
