"""Punto de entrada de `make entrenar-clasificador-fenomenos` (ADR 0024; I4, Fase 9 reabierta).

Lee `data/private/anotacion_fenomenos/calificaciones.csv` (nunca la lee Claude Code) y los
embeddings de relato ya calculados por `make nlp` (`data/embeddings/<lote_id>/segmento.parquet`).
Antes de entrenar, exige la compuerta de `decla.fenomenos.clasificador.exigir_cobertura_minima`
(CLAUDE.md §2.3): si algún código no tiene suficientes ejemplos anotados, termina con un mensaje
claro y no entrena nada. Con la compuerta superada, entrena, evalúa con partición temporal sobre
`entidades.noticia_criminal.fecha_hecho` y escribe `fenomenos.asignacion_fenomeno_modelo`
(`origen="inferido_modelo"`) — nunca sobrescribe `fenomenos.asignacion_fenomeno` (la de
clustering, Fase 6, CLAUDE.md §2.4).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import conectar, escribir_tabla_polars
from decla.comun.ejecucion import RegistroEjecucion
from decla.fenomenos.clasificador import (
    entrenar_clasificador,
    evaluar_particion_temporal,
    exigir_cobertura_minima,
    predecir_codigos,
)
from decla.fenomenos.herramienta_anotacion_fenomeno import (
    NO_CLASIFICADO,
    RUTA_CALIFICACIONES_DEFECTO,
    RUTA_TAXONOMIA_DEFECTO,
    calcular_cobertura_por_codigo,
    cargar_calificaciones_fenomeno,
    cargar_codigos_fenomeno,
    codigos_efectivos,
)
from decla.fenomenos.orquestador import RUTA_EMBEDDINGS_DEFECTO
from decla.fenomenos.representacion import cargar_embeddings_segmento

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_UMBRALES = RAIZ_PROYECTO / "config" / "umbrales.yaml"
RUTA_METRICAS_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "i4" / "clasificador_fenomenos_metricas.md"
)


def _codigos_entrenables(ruta_taxonomia: Path) -> list[str]:
    """Códigos que el clasificador predice: todos menos `no_clasificado` (ese es "ninguno de los
    anteriores superó el umbral", no una columna que se entrena — igual criterio que
    `zero_shot.NO_CLASIFICADO`)."""
    return [c for c in cargar_codigos_fenomeno(ruta_taxonomia) if c != NO_CLASIFICADO]


def _construir_matriz_etiquetas(
    calificaciones: list[dict[str, str]], registros_uid: list[str], codigos: list[str]
) -> np.ndarray:
    por_registro = {fila["registro_uid"]: codigos_efectivos(fila) for fila in calificaciones}
    matriz = np.zeros((len(registros_uid), len(codigos)), dtype=int)
    for fila_idx, uid in enumerate(registros_uid):
        codigos_fila = por_registro.get(uid, [])
        for col_idx, codigo in enumerate(codigos):
            if codigo in codigos_fila:
                matriz[fila_idx, col_idx] = 1
    return matriz


def _escribir_metricas(metricas: list[Any], ruta_salida: Path) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Clasificador de fenómenos — evaluación con partición temporal (ADR 0024)",
        "",
        "| código | precisión | exhaustividad | F1 | positivos en prueba |",
        "|---|---|---|---|---|",
    ]
    for m in metricas:
        lineas.append(
            f"| {m.codigo} | {m.precision} | {m.exhaustividad} | {m.f1} | "
            f"{m.n_positivos_prueba} |"
        )
    ruta_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def ejecutar_entrenamiento(
    ruta_duckdb: Path,
    lote_id: str,
    ruta_calificaciones: Path = RUTA_CALIFICACIONES_DEFECTO,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DEFECTO,
    ruta_taxonomia: Path = RUTA_TAXONOMIA_DEFECTO,
    ruta_umbrales: Path = RUTA_UMBRALES,
    ruta_metricas: Path = RUTA_METRICAS_DEFECTO,
) -> tuple[str, int]:
    codigos = _codigos_entrenables(ruta_taxonomia)
    calificaciones = cargar_calificaciones_fenomeno(ruta_calificaciones)

    umbrales = cargar_yaml(ruta_umbrales)["clasificador_fenomeno"]
    cobertura = calcular_cobertura_por_codigo(calificaciones, codigos)
    exigir_cobertura_minima(cobertura, umbrales["minimo_ejemplos_por_codigo"])
    confianza_minima = umbrales["confianza_minima"]
    if not isinstance(confianza_minima, (int, float)):
        raise ValueError(
            "config/umbrales.yaml: clasificador_fenomeno.confianza_minima sigue "
            "'pendiente_de_calibrar' — calíbralo con la muestra anotada antes de usar el modelo "
            "para reclasificar (CLAUDE.md: no inventar un umbral sin evidencia)."
        )

    embeddings = cargar_embeddings_segmento(ruta_embeddings_datos / lote_id / "segmento.parquet")
    registros_uid = sorted(set(embeddings) & {fila["registro_uid"] for fila in calificaciones})
    X = np.array([embeddings[uid] for uid in registros_uid])
    Y = _construir_matriz_etiquetas(calificaciones, registros_uid, codigos)

    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(
            conexion, paso="entrenar_clasificador_fenomenos", parametros={"lote_id": lote_id}
        ) as registro:
            fechas = conexion.sql(
                "SELECT registro_uid, fecha_hecho FROM entidades.noticia_criminal"
            ).pl()
            fechas_por_uid = dict(
                zip(fechas["registro_uid"].to_list(), fechas["fecha_hecho"].to_list(), strict=True)
            )
            fechas_por_uid = {
                uid: fecha for uid, fecha in fechas_por_uid.items() if uid in set(registros_uid)
            }
            fechas_ordenadas = sorted(str(fechas_por_uid[uid]) for uid in registros_uid)
            fecha_corte = fechas_ordenadas[int(len(fechas_ordenadas) * 0.8)]
            fechas_lista = [str(fechas_por_uid[uid]) for uid in registros_uid]

            metricas = evaluar_particion_temporal(X, Y, fechas_lista, codigos, fecha_corte)
            _escribir_metricas(metricas, ruta_metricas)

            modelo_fenomeno = entrenar_clasificador(X, Y, codigos)
            predicciones = predecir_codigos(modelo_fenomeno, X, confianza_minima)

            version_modelo = f"clasificador_fenomenos-v1-{registro.run_id[:8]}"
            filas = [
                {
                    "registro_uid": uid,
                    "codigo_fenomeno": codigo,
                    "origen": "inferido_modelo",
                    "confianza": confianza_minima,
                    "version_modelo": version_modelo,
                    "run_id": registro.run_id,
                }
                for uid, codigos_predichos in zip(registros_uid, predicciones, strict=True)
                for codigo in (codigos_predichos or [NO_CLASIFICADO])
            ]
            escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno_modelo", filas)
            n_filas = len(filas)
    finally:
        conexion.close()

    return version_modelo, n_filas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--lote-id", required=True, help="lote_id usado en `make nlp`.")
    args: Any = parser.parse_args(argv)

    version_modelo, n_filas = ejecutar_entrenamiento(args.duckdb, args.lote_id)
    print(f"Clasificador de fenómenos entrenado: {version_modelo} ({n_filas} filas escritas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
