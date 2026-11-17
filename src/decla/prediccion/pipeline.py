"""Punto de entrada de `make prediccion` (I4, Fase 9 — atípicos y pronósticos; clasificación
temática sigue sin entrenarse por falta de anotación real, aunque su infraestructura ya existe
—`make anotar-fenomenos` / `make entrenar-clasificador-fenomenos`, ADR 0024—, ver
`reports/agregados/i4/viabilidad.md` y `docs/informes/I4_cierre.md`).

Pronósticos reabiertos por ADR 0016 (2026-11-05): ya no exigen ≥36 meses de historia — se
construyen con lo disponible, con modelo ingenuo obligatorio, sin estacionalidad (<12 meses) e
intervalos anchos declarados explícitamente (`decla.prediccion.pronosticos`).

Lee `data/warehouse.duckdb` en lectura-escritura (deben existir ya `make etl`, `make nlp`,
`make conocimiento`, `make fenomenos`, `scripts/congelar_taxonomia_v1.py` y `make analitica`,
que materializa `fenomenos.asignacion_fenomeno`) y escribe `oro.atipicos`, `oro.pronosticos`
y `oro.pronosticos_delito` ahí. Esta última serie por `delito_nombre` (en vez de
`codigo_fenomeno`) distingue el tipo de delito en tendencia, dado que el clustering de
fenómenos converge en un solo grupo dominante (ADR 0014, ADR 2026-11-06-pronosticos-por-delito).
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
    procesar_pronosticos_delito,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def ejecutar_prediccion(
    ruta_duckdb: Path,
    lote_id_embeddings: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DEFECTO,
    horizonte_pronostico: int = 3,
) -> tuple[str, ResumenAtipicos, ResumenPronosticos, ResumenPronosticos]:
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
            resumen_pronosticos_delito = procesar_pronosticos_delito(
                conexion, run_id, horizonte=horizonte_pronostico
            )
    finally:
        conexion.close()
    return run_id, resumen_atipicos, resumen_pronosticos, resumen_pronosticos_delito


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", required=True, help="lote_id usado en `make nlp`.")
    parser.add_argument("--embeddings", type=Path, default=RUTA_EMBEDDINGS_DEFECTO)
    parser.add_argument("--horizonte", type=int, default=3)
    args: Any = parser.parse_args(argv)

    run_id, resumen_atipicos, resumen_pronosticos, resumen_pronosticos_delito = ejecutar_prediccion(
        args.duckdb, args.lote_id, args.embeddings, args.horizonte
    )

    print(f"Predicción completa — run_id={run_id}")
    print(f"  Atípicos: {resumen_atipicos.n_registros} registros evaluados")
    print(
        f"  Pronósticos (fenómeno): {resumen_pronosticos.n_series_evaluadas} series evaluadas, "
        f"{resumen_pronosticos.n_filas_escritas} filas escritas en oro.pronosticos"
    )
    print(
        f"  Pronósticos (delito): {resumen_pronosticos_delito.n_series_evaluadas} series "
        f"evaluadas, {resumen_pronosticos_delito.n_filas_escritas} filas escritas en "
        "oro.pronosticos_delito"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
