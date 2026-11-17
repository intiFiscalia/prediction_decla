"""Punto de entrada de `make clasificar-fenomenos-llm` (ADR 0027, reemplaza la cascada de ADR
0026): el LLM local clasifica el 100% de los relatos — no hay clasificador rápido filtrando qué
revisar. Por defecto solo procesa `registro_uid` que todavía no tengan una fila
`origen="inferido_modelo_llm"` (reprocesamiento incremental entre lotes); `--forzar` reclasifica
todo, para cuando se itera el prompt y hay que ver el efecto sobre toda la muestra de nuevo.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any

import duckdb

from decla.comun.duckdb_io import conectar, escribir_tabla_polars, tabla_existe
from decla.comun.ejecucion import RegistroEjecucion
from decla.fenomenos.clasificador_llm import ClienteLLM, ClienteMLX, clasificar_relato
from decla.fenomenos.herramienta_anotacion_fenomeno import (
    NO_CLASIFICADO,
    RUTA_TAXONOMIA_DEFECTO,
    cargar_codigos_fenomeno,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_MODELO_LLM_DEFECTO = RAIZ_PROYECTO / "models" / "qwen2.5-14b-instruct-4bit"
ORIGEN_LLM = "inferido_modelo_llm"
SEMILLA_MUESTREO_DEFECTO = 20260101


def _escribir_fila_opcional(
    conexion: duckdb.DuckDBPyConnection, tabla: str, fila: dict[str, Any], tabla_existe_ya: bool
) -> bool:
    """Escribe una sola fila en una tabla secundaria opcional (organización mencionada, fenómeno
    no listado — ADR 0028/0029): mismo patrón de "reemplazar solo la primera vez, agregar
    después" que la tabla principal. Devuelve si la tabla ya existe, para que quien llama
    actualice su propio flag entre iteraciones."""
    modo = "reemplazar" if not tabla_existe_ya else "agregar"
    escribir_tabla_polars(conexion, "fenomenos", tabla, [fila], modo=modo)
    return True


def _relatos_pendientes(
    conexion: duckdb.DuckDBPyConnection,
    forzar: bool,
    limite: int | None = None,
    semilla_muestreo: int = SEMILLA_MUESTREO_DEFECTO,
) -> list[dict[str, Any]]:
    if not forzar and tabla_existe(conexion, "fenomenos", "asignacion_fenomeno_modelo"):
        consulta = (
            "SELECT registro_uid, relato_enmascarado FROM texto.relato_procesado "
            "WHERE registro_uid NOT IN ("
            "  SELECT registro_uid FROM fenomenos.asignacion_fenomeno_modelo "
            f"  WHERE origen = '{ORIGEN_LLM}'"
            ")"
        )
    else:
        consulta = "SELECT registro_uid, relato_enmascarado FROM texto.relato_procesado"
    consulta += " ORDER BY registro_uid"
    filas = conexion.sql(consulta).pl().to_dicts()
    # Muestra reproducible (CLAUDE.md §2.4): mismo `limite` y semilla siempre devuelven el mismo
    # subconjunto, para que iterar el prompt entre corridas sea comparable — útil mientras la
    # data es de prueba/entrenamiento y no hace falta procesar los 346 relatos cada vez.
    if limite is not None and len(filas) > limite:
        filas = random.Random(semilla_muestreo).sample(filas, limite)
    return filas


def ejecutar_clasificacion_llm(
    ruta_duckdb: Path,
    cliente: ClienteLLM,
    ruta_taxonomia: Path = RUTA_TAXONOMIA_DEFECTO,
    forzar: bool = False,
    limite: int | None = None,
) -> tuple[str, int, int, int, int, list[str]]:
    """Escribe cada relato apenas se clasifica (no acumula en memoria para un solo INSERT al
    final): una corrida de horas no debe perder todo el trabajo hecho por un error en una sola
    fila. Un relato que falla (JSON inválido, código desconocido, lo que sea) se salta — como no
    queda fila `origen="inferido_modelo_llm"` para ese `registro_uid`, la próxima corrida
    incremental (sin `--forzar`) lo reintenta sola, nunca se descarta en silencio.
    """
    codigos_disponibles = cargar_codigos_fenomeno(ruta_taxonomia)

    conexion = conectar(ruta_duckdb, solo_lectura=False)
    try:
        with RegistroEjecucion(
            conexion, paso="clasificar_fenomenos_llm", parametros={"forzar": forzar}
        ) as registro:
            tabla_fenomeno_existe = tabla_existe(
                conexion, "fenomenos", "asignacion_fenomeno_modelo"
            )
            tabla_org_existe = tabla_existe(conexion, "fenomenos", "organizacion_mencion_modelo")
            tabla_no_listado_existe = tabla_existe(
                conexion, "fenomenos", "fenomeno_no_listado_modelo"
            )
            relatos = _relatos_pendientes(conexion, forzar, limite)

            version_modelo = f"clasificador_fenomenos_llm-qwen2.5-14b-v1-{registro.run_id[:8]}"
            n_ok = 0
            n_filas = 0
            n_organizaciones = 0
            n_no_listados = 0
            registros_fallidos: list[str] = []
            for indice, fila in enumerate(relatos, start=1):
                try:
                    resultado = clasificar_relato(
                        cliente, fila["relato_enmascarado"], codigos_disponibles
                    )
                except Exception as error:  # noqa: BLE001 — un relato malo no debe tumbar la corrida
                    registros_fallidos.append(fila["registro_uid"])
                    print(f"  [{indice}/{len(relatos)}] error en {fila['registro_uid']}: {error}")
                    continue

                filas_relato = [
                    {
                        "registro_uid": fila["registro_uid"],
                        "codigo_fenomeno": codigo,
                        "origen": ORIGEN_LLM,
                        "confianza": resultado.confianza,
                        "version_modelo": version_modelo,
                        "run_id": registro.run_id,
                    }
                    for codigo in (resultado.codigos or [NO_CLASIFICADO])
                ]
                # La tabla se crea en modo "reemplazar" solo la primera vez que no existe; de ahí
                # en adelante siempre se agrega (INSERT) — ni entre relatos de esta misma corrida
                # ni entre corridas se pierde lo ya escrito (CLAUDE.md §2.4).
                modo = "reemplazar" if not tabla_fenomeno_existe else "agregar"
                escribir_tabla_polars(
                    conexion, "fenomenos", "asignacion_fenomeno_modelo", filas_relato, modo=modo
                )
                tabla_fenomeno_existe = True
                n_ok += 1
                n_filas += len(filas_relato)

                # Organización criminal mencionada (ADR 0028) y fenómeno no listado (ADR 0029):
                # campos abiertos, raros en los datos — solo se escriben cuando el LLM encontró
                # algo explícito, nunca se fuerzan.
                if resultado.organizacion_mencionada:
                    tabla_org_existe = _escribir_fila_opcional(
                        conexion,
                        "organizacion_mencion_modelo",
                        {
                            "registro_uid": fila["registro_uid"],
                            "organizacion_nombre_crudo": resultado.organizacion_mencionada,
                            "confianza": resultado.confianza,
                            "origen": ORIGEN_LLM,
                            "version_modelo": version_modelo,
                            "run_id": registro.run_id,
                        },
                        tabla_org_existe,
                    )
                    n_organizaciones += 1

                if resultado.fenomeno_no_listado:
                    tabla_no_listado_existe = _escribir_fila_opcional(
                        conexion,
                        "fenomeno_no_listado_modelo",
                        {
                            "registro_uid": fila["registro_uid"],
                            "texto_crudo": resultado.fenomeno_no_listado,
                            "confianza": resultado.confianza,
                            "origen": ORIGEN_LLM,
                            "version_modelo": version_modelo,
                            "run_id": registro.run_id,
                        },
                        tabla_no_listado_existe,
                    )
                    n_no_listados += 1

                print(f"  [{indice}/{len(relatos)}] {fila['registro_uid']}: ok")
    finally:
        conexion.close()

    return version_modelo, n_ok, n_filas, n_organizaciones, n_no_listados, registros_fallidos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--modelo-llm", type=Path, default=RUTA_MODELO_LLM_DEFECTO)
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Reclasifica todos los relatos, no solo los pendientes (usar al iterar el prompt).",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help=(
            "Procesa como máximo N relatos (muestra aleatoria con semilla fija, reproducible) "
            "en vez del universo completo — útil para iterar rápido mientras la data es de "
            "prueba/entrenamiento."
        ),
    )
    args: Any = parser.parse_args(argv)

    cliente = ClienteMLX(args.modelo_llm)
    version_modelo, n_ok, n_filas, n_organizaciones, n_no_listados, registros_fallidos = (
        ejecutar_clasificacion_llm(args.duckdb, cliente, forzar=args.forzar, limite=args.limite)
    )
    print(
        f"Clasificador LLM: {n_ok} relatos clasificados ({n_filas} filas escritas) como "
        f"{version_modelo}. {n_organizaciones} relatos mencionaron una organización explícita; "
        f"{n_no_listados} describieron un fenómeno no listado en la taxonomía."
    )
    if registros_fallidos:
        print(
            f"  {len(registros_fallidos)} relatos fallaron y quedan pendientes para la próxima "
            f"corrida (sin --forzar): {registros_fallidos}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
