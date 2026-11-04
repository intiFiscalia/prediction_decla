"""Punto de entrada de `make emergencia` (Fase 8, I3).

Lee `data/warehouse.duckdb` en lectura-escritura (debe existir ya, vía `make etl` + `make nlp` +
`make conocimiento` + `make fenomenos` + `scripts/congelar_taxonomia_v1.py`) y escribe
`oro.alertas` ahí.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion
from decla.emergencia.orquestador import ResumenEmergencia, procesar_emergencia

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_UMBRALES_DEFECTO = RAIZ_PROYECTO / "config" / "umbrales.yaml"


def ejecutar_emergencia(ruta_duckdb: Path, ruta_umbrales: Path) -> tuple[str, ResumenEmergencia]:
    run_id = str(uuid.uuid4())
    umbrales = cargar_yaml(ruta_umbrales)["emergencia"]
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(conexion, paso="emergencia"):
            resumen = procesar_emergencia(conexion, run_id, umbrales)
    finally:
        conexion.close()
    return run_id, resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--umbrales", type=Path, default=RUTA_UMBRALES_DEFECTO)
    args: Any = parser.parse_args(argv)

    run_id, resumen = ejecutar_emergencia(args.duckdb, args.umbrales)

    print(f"Emergencia completa — run_id={run_id}")
    print(f"  Series evaluadas: {resumen.n_series_evaluadas}")
    print(f"  Candidatos en observación: {resumen.n_candidatos}")
    print(f"  Alertas: {resumen.n_alertas}")
    print(f"  Descartadas por posible artefacto: {resumen.n_descartadas_por_artefacto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
