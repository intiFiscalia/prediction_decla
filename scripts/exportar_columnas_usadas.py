"""Exporta CASOS y RELATOS originales con solo las columnas que el pipeline (`plata` en
adelante) realmente usa, para que la persona los lea más fácil (CLAUDE.md §2.1: Claude Code
nunca abre `data/raw/` ni esta salida — la persona la ejecuta y la lee en su equipo).

La lista de columnas usadas se basa en `decla.normalizacion` (qué columna de CASOS alimenta cada
columna de `plata.registros_limpios`) y `config/alcance_tematico.yaml` (filtro de alcance, ADR
0008). No se inventa la lista: cada columna incluida tiene una referencia real en el código.

Columnas de CASOS que se excluyen porque ningún módulo de `plata`/`entidades`/`texto`/
`conocimiento`/`analitica`/`emergencia`/`prediccion` las usa (solo aparecieron en el diagnóstico
de calidad de I0, ya cerrado): CASO_LEY, LEY, ULTIMA_ACTUACION (texto; se conserva la fecha
FECHA_ULTIMA_ACTUACION), OTROS_DELITOS, RUPTURA, DESP_CONOCIDO_CASO_TIT,
DESP_CONOCIDO_CASO_APOYO, CASO_GRUPO_ESPECIALIZADO, "Eje temático APLICA",
"eje tmeatico APLICA", EJE_TEMATICO, UNID_DESCRIPCION. Si se decide usar alguna de estas más
adelante, se agrega a `COLUMNAS_CASOS_USADAS` y se vuelve a correr este script — no hace falta
tocar `data/raw/`.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from decla.ingesta.lectores import TablaLeida, leer_tabla, localizar_archivo

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]

# Obligatorias (config/esquema_fuente.yaml) + opcionales con uso real confirmado en
# decla.normalizacion o en el filtro de alcance (config/alcance_tematico.yaml, ADR 0008).
COLUMNAS_CASOS_USADAS = [
    "CASO_NOTICIA", "CASO_ID", "DESP_ID",
    "TIPO_NOTICIA", "ESTADO", "ETAPA", "TIPO_DILIGENCIA",
    "FECHA_HECHO", "CASO_FECHA_DENUNCIA", "FECHA_CREACION", "CASO_FECHA_REG_NC",
    "FECHA_ASIGNACION", "CASO_FECHA_PRESCRIPCION",
    "FECHA_ULTIMA_ACTUACION", "FECHA_REGISTRO_ACTUACION",
    "DELITO", "TITULO", "CAPITULO", "SECC_DESCRIPCION",
    "NO_CASOS_CONEXOS", "COMPETENCIA_DESPACHO",
    "DEPARTAMENTO_HECHOS", "MUNICIPIO_HECHOS", "DEPARTAMENTO_UNIDAD", "MUNICIPIO_UNIDAD",
    "LAT_DIR_HECHOS", "LONG_DIR_HECHOS",
    "NUMERO_DOCUMENTO", "FISCAL_ASIGNADO_DESPACHO", "DESPACHO",
]
COLUMNAS_RELATOS_USADAS = ["CASO_NOTICIA", "RELATO"]


def _escribir_csv_filtrado(tabla: TablaLeida, columnas_usadas: list[str], ruta_salida: Path) -> int:
    columnas_presentes = [c for c in columnas_usadas if c in tabla.columnas]
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas_presentes)
        escritor.writeheader()
        for fila in tabla.filas:
            escritor.writerow({c: fila.get(c) for c in columnas_presentes})
    return len(columnas_presentes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RAIZ_PROYECTO / "data" / "raw")
    parser.add_argument(
        "--salida", type=Path, default=RAIZ_PROYECTO / "data" / "private" / "columnas_usadas"
    )
    args = parser.parse_args(argv)

    archivo_casos = localizar_archivo(args.entrada, "CASOS")
    archivo_relatos = localizar_archivo(args.entrada, "RELATOS")
    if archivo_casos is None or archivo_relatos is None:
        raise FileNotFoundError(f"No se encontró CASOS o RELATOS en {args.entrada}")

    tabla_casos = leer_tabla(archivo_casos)
    tabla_relatos = leer_tabla(archivo_relatos)

    n_casos = _escribir_csv_filtrado(
        tabla_casos, COLUMNAS_CASOS_USADAS, args.salida / "casos_columnas_usadas.csv"
    )
    n_relatos = _escribir_csv_filtrado(
        tabla_relatos, COLUMNAS_RELATOS_USADAS, args.salida / "relatos_columnas_usadas.csv"
    )

    print(f"CASOS: {tabla_casos.n_filas_total} filas, {n_casos} columnas -> {args.salida}")
    print(f"RELATOS: {tabla_relatos.n_filas_total} filas, {n_relatos} columnas -> {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
