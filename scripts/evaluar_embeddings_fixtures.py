"""Compara modelos de embeddings sobre `tests/fixtures/` (plan_trabajo.md §5.2, §6.1 paso 8;
CLAUDE.md §4.20; mini-compuerta 2A). Solo fixtures sintéticas con verdad de terreno
(`fenomeno_plantado`): la comparación con pares reales calificados por analistas se hace con
`texto/herramienta_anotacion_pares.py` por separado (esta corrida no la sustituye).

Escribe `reports/agregados/i2/embeddings.md` con precisión@k por modelo y agregación, y tiempo
y RAM aproximados (CLAUDE.md §2.4: nada de esto toca datos reales ni `data/raw/`).

Uso:
    uv run python scripts/evaluar_embeddings_fixtures.py
    uv run python scripts/evaluar_embeddings_fixtures.py --k 10 --modelos bge-m3
"""

from __future__ import annotations

import argparse
import resource
import time
from pathlib import Path

import polars as pl

from decla.texto.comparacion_modelos import MEDIA, RelatoEtiquetado, comparar_modelos

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_FIXTURES = RAIZ_PROYECTO / "tests" / "fixtures"
RUTA_VERDAD = RUTA_FIXTURES / "verdad.parquet"
RUTA_RELATOS = RUTA_FIXTURES / "relatos_sinteticos.csv"
RUTA_SALIDA_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "i2" / "embeddings.md"

MODELOS_DEFECTO = [
    "paraphrase-multilingual-mpnet-base-v2",
    "multilingual-e5-base",
    "bge-m3",
]


def cargar_relatos_etiquetados(
    ruta_verdad: Path = RUTA_VERDAD, ruta_relatos: Path = RUTA_RELATOS
) -> list[RelatoEtiquetado]:
    verdad = pl.read_parquet(ruta_verdad)
    relatos = pl.read_csv(ruta_relatos, infer_schema_length=0)
    combinado = verdad.join(
        relatos, left_on="caso_noticia", right_on="CASO_NOTICIA", how="inner"
    )
    return [
        RelatoEtiquetado(fila["relato_id"], fila["RELATO"], fila["fenomeno_plantado"])
        for fila in combinado.iter_rows(named=True)
        if fila["RELATO"]
    ]


def _ram_actual_mb() -> float:
    # macOS reporta ru_maxrss en bytes; Linux en KB. ADR 0001 fija macOS como objetivo, así que
    # se divide como bytes; en Linux esta cifra quedaría ~1000x inflada (documentado aquí, no se
    # corrige en caliente para no adivinar la plataforma).
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2)


def ejecutar_comparacion(
    nombres_modelos: list[str], k: int, agregacion: str = MEDIA
) -> tuple[list, dict[str, float]]:
    relatos = cargar_relatos_etiquetados()
    resultados = []
    tiempos_por_modelo: dict[str, float] = {}
    for nombre_modelo in nombres_modelos:
        inicio = time.perf_counter()
        resultados.extend(comparar_modelos(relatos, [nombre_modelo], k=k, agregacion=agregacion))
        tiempos_por_modelo[nombre_modelo] = round(time.perf_counter() - inicio, 2)
    return resultados, tiempos_por_modelo


def escribir_informe(
    resultados: list, tiempos_por_modelo: dict[str, float], ram_mb: float, ruta_salida: Path
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Comparación de modelos de embeddings (fixtures sintéticas)",
        "",
        "Precisión@k de recuperación del `fenomeno_plantado` entre los k vecinos más cercanos "
        "por coseno. Medida indicativa sobre datos sintéticos; la elección final también pondera "
        "pares reales calificados por analistas (ver `herramienta_anotacion_pares.py`).",
        "",
        "| Modelo | Agregación | k | Precisión@k | n_relatos | Tiempo (s) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for resultado in resultados:
        tiempo = tiempos_por_modelo.get(resultado.nombre_modelo, "?")
        lineas.append(
            f"| {resultado.nombre_modelo} | {resultado.agregacion} | {resultado.k} | "
            f"{resultado.precision_en_k} | {resultado.n_relatos} | {tiempo} |"
        )
    lineas += [
        "",
        f"RAM aproximada al final de la corrida: {ram_mb:.0f} MB (ver nota de unidad arriba).",
    ]
    ruta_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--modelos", nargs="+", default=MODELOS_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_SALIDA_DEFECTO)
    args = parser.parse_args(argv)

    resultados, tiempos_por_modelo = ejecutar_comparacion(args.modelos, args.k)
    escribir_informe(resultados, tiempos_por_modelo, _ram_actual_mb(), args.salida)
    print(f"Comparación de embeddings escrita en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
