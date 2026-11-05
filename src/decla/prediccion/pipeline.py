"""Punto de entrada de `make prediccion` (I4, Fase 9 — atípicos y pronósticos; clasificación
temática no es viable todavía por falta de anotación, ver `reports/agregados/i4/viabilidad.md`
y `docs/informes/I4_cierre.md`).

Pronósticos reabiertos por ADR 0016 (2026-11-05): ya no exigen ≥36 meses de historia — se
construyen con lo disponible, con modelo ingenuo obligatorio, sin estacionalidad (<12 meses) e
intervalos anchos declarados explícitamente (`decla.prediccion.pronosticos`).

Lee `data/warehouse.duckdb` en lectura-escritura (deben existir ya `make etl`, `make nlp`,
`make conocimiento`, `make fenomenos`, `scripts/congelar_taxonomia_v1.py` y `make analitica`,
que materializa `fenomenos.asignacion_fenomeno`) y escribe `oro.atipicos` y `oro.pronosticos`
ahí.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.fenomenos.orquestador import RUTA_EMBEDDINGS_DEFECTO
from decla.prediccion.orquestador import (
    ResumenAtipicos,
    ResumenPronosticos,
    procesar_atipicos,
    procesar_pronosticos,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def ejecutar_prediccion(
    ruta_duckdb: Path,
    lote_id_embeddings: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DEFECTO,
    horizonte_pronostico: int = 3,
) -> tuple[str, ResumenAtipicos, ResumenPronosticos]:
    run_id = str(uuid.uuid4())
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    parametros = {"lote_id": lote_id_embeddings, "horizonte_pronostico": horizonte_pronostico}
    try:
        with RegistroEjecucion(conexion, paso="prediccion", parametros=parametros):
            resumen_atipicos = procesar_atipicos(
                conexion, lote_id_embeddings, ruta_embeddings_datos, run_id
            )
            resumen_pronosticos = procesar_pronosticos(
                conexion, run_id, horizonte=horizonte_pronostico
            )
    finally:
        conexion.close()
    return run_id, resumen_atipicos, resumen_pronosticos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", required=True, help="lote_id usado en `make nlp`.")
    parser.add_argument("--embeddings", type=Path, default=RUTA_EMBEDDINGS_DEFECTO)
    parser.add_argument("--horizonte", type=int, default=3)
    args: Any = parser.parse_args(argv)

    run_id, resumen_atipicos, resumen_pronosticos = ejecutar_prediccion(
        args.duckdb, args.lote_id, args.embeddings, args.horizonte
    )

    print(f"Predicción completa — run_id={run_id}")
    print(f"  Atípicos: {resumen_atipicos.n_registros} registros evaluados")
    print(
        f"  Pronósticos: {resumen_pronosticos.n_series_evaluadas} series evaluadas, "
        f"{resumen_pronosticos.n_filas_escritas} filas escritas en oro.pronosticos"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
