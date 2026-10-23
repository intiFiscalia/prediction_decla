"""Prueba de humo del incremento 00: el paquete se importa y el generador de fixtures corre
de extremo a extremo en un directorio temporal, sin tocar `data/raw/` ni `data/private/`.
"""

import subprocess
import sys
from pathlib import Path

import decla
import decla.comun.configuracion
import decla.comun.duckdb_io
import decla.comun.ejecucion
import decla.comun.entorno
import decla.comun.registro
import decla.comun.supresion

RAIZ = Path(__file__).resolve().parents[2]


def test_el_paquete_decla_se_importa() -> None:
    assert decla is not None


def test_generador_de_fixtures_corre_de_extremo_a_extremo(tmp_path: Path) -> None:
    destino = tmp_path / "fixtures"
    subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts" / "generar_fixtures.py"),
            "--seed",
            "1",
            "--n-noticias",
            "20",
            "--destino",
            str(destino),
        ],
        check=True,
        cwd=RAIZ,
    )
    assert (destino / "casos_sinteticos.csv").exists()
    assert (destino / "relatos_sinteticos.csv").exists()
    assert (destino / "verdad.parquet").exists()
