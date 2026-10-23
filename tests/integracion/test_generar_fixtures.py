"""Prueba de integración del generador de fixtures (CLAUDE.md §4; AC del incremento 00):
reproducibilidad exacta con la misma semilla y presencia de los cinco artefactos esperados.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVOS_ESPERADOS = {
    "casos_sinteticos.csv",
    "casos_sinteticos.xlsx",
    "relatos_sinteticos.csv",
    "relatos_sinteticos.xlsx",
    "verdad.parquet",
}


def _generar(destino: Path, seed: int = 123, n: int = 30) -> None:
    subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts" / "generar_fixtures.py"),
            "--seed",
            str(seed),
            "--n-noticias",
            str(n),
            "--destino",
            str(destino),
        ],
        check=True,
        cwd=RAIZ,
    )


def _hashes(destino: Path) -> dict[str, str]:
    return {
        nombre: hashlib.sha256((destino / nombre).read_bytes()).hexdigest()
        for nombre in ARCHIVOS_ESPERADOS
    }


def test_genera_los_archivos_esperados(tmp_path: Path) -> None:
    destino = tmp_path / "salida"
    _generar(destino)
    assert {p.name for p in destino.iterdir()} == ARCHIVOS_ESPERADOS


def test_misma_semilla_produce_hashes_identicos(tmp_path: Path) -> None:
    destino_a, destino_b = tmp_path / "a", tmp_path / "b"
    _generar(destino_a, seed=321, n=25)
    _generar(destino_b, seed=321, n=25)
    assert _hashes(destino_a) == _hashes(destino_b)


def test_semillas_distintas_producen_salidas_distintas(tmp_path: Path) -> None:
    destino_a, destino_b = tmp_path / "a", tmp_path / "b"
    _generar(destino_a, seed=1, n=25)
    _generar(destino_b, seed=2, n=25)
    assert _hashes(destino_a) != _hashes(destino_b)
