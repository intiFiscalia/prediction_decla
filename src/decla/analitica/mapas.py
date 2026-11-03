"""Mapas territoriales y matriz origen-destino (plan_trabajo.md §8.2).

Usa la cartografía real descargada en I1 (`data/referencia/cartografia/`); misma escala entre
periodos vía `vmin`/`vmax`; cada mapa incluye el % de registros con territorio resuelto. No se
hace análisis de punto más fino que la precisión disponible (CLAUDE.md §4.17: ~3 decimales,
~100 m).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CARTOGRAFIA_DEPARTAMENTOS = (
    RAIZ_PROYECTO / "data" / "referencia" / "cartografia" / "departamentos.geojson"
)
RUTA_CARTOGRAFIA_MUNICIPIOS = (
    RAIZ_PROYECTO / "data" / "referencia" / "cartografia" / "municipios.geojson"
)

NOTA_ACTIVIDAD_REGISTRADA = "Actividad institucional registrada, no incidencia real del delito."


def matriz_origen_destino(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Unidad: registro. Filas = departamento de los HECHOS, columnas = departamento de la
    UNIDAD que tramita. Una alta proporción fuera de la diagonal puede reflejar competencias
    especializadas, no movilidad del delito (plan_trabajo.md §8.2).
    """
    return conexion.sql(
        """
        SELECT cod_dpto_hechos, cod_dpto_unidad, count(*) AS n_registros
        FROM plata.registros_limpios
        WHERE cod_dpto_hechos IS NOT NULL AND cod_dpto_unidad IS NOT NULL
        GROUP BY cod_dpto_hechos, cod_dpto_unidad
        ORDER BY cod_dpto_hechos, cod_dpto_unidad
        """
    ).pl()


def _pct_territorio_resuelto(conexion: duckdb.DuckDBPyConnection, columna: str) -> float:
    resultado = conexion.sql(
        f"""
        SELECT round(
            count(*) FILTER (WHERE {columna} IS NOT NULL) * 100.0 / count(*), 1
        ) AS pct
        FROM plata.registros_limpios
        """
    ).pl()
    valor = resultado["pct"].item()
    return float(valor) if valor is not None else 0.0


def _generar_mapa(
    conexion: duckdb.DuckDBPyConnection,
    ruta_cartografia: Path,
    columna_codigo_cartografia: str,
    columna_codigo_registros: str,
    titulo: str,
    ruta_salida: Path,
    vmin: float | None,
    vmax: float | None,
) -> None:
    conteo = conexion.sql(
        f"""
        SELECT {columna_codigo_registros} AS codigo, count(*) AS n_registros
        FROM plata.registros_limpios
        WHERE {columna_codigo_registros} IS NOT NULL
        GROUP BY {columna_codigo_registros}
        """
    ).pl()
    geo = gpd.read_file(ruta_cartografia)
    geo = geo.merge(
        conteo.to_pandas(), left_on=columna_codigo_cartografia, right_on="codigo", how="left"
    )
    geo["n_registros"] = geo["n_registros"].fillna(0)

    pct_resuelto = _pct_territorio_resuelto(conexion, columna_codigo_registros)

    fig, ax = plt.subplots(figsize=(8, 10))
    geo.plot(
        column="n_registros", cmap="OrRd", linewidth=0.2, edgecolor="grey",
        legend=True, ax=ax, vmin=vmin, vmax=vmax,
    )
    ax.set_title(f"{titulo}\n{NOTA_ACTIVIDAD_REGISTRADA}", fontsize=10)
    ax.axis("off")
    fig.text(
        0.5, 0.02, f"Territorio resuelto: {pct_resuelto}% de los registros",
        ha="center", fontsize=8,
    )
    fig.tight_layout()
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_salida, dpi=120)
    plt.close(fig)


def generar_mapa_departamental(
    conexion: duckdb.DuckDBPyConnection,
    ruta_salida: Path,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    _generar_mapa(
        conexion, RUTA_CARTOGRAFIA_DEPARTAMENTOS, "divipola_dep", "cod_dpto_hechos",
        "Noticias por departamento de los hechos", ruta_salida, vmin, vmax,
    )


def generar_mapa_municipal(
    conexion: duckdb.DuckDBPyConnection,
    ruta_salida: Path,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    _generar_mapa(
        conexion, RUTA_CARTOGRAFIA_MUNICIPIOS, "divipola_mun", "cod_mpio_hechos",
        "Noticias por municipio de los hechos", ruta_salida, vmin, vmax,
    )


def generar_mapa_flujos(
    conexion: duckdb.DuckDBPyConnection,
    ruta_salida: Path,
    umbral_minimo_flujo: int = 1,
) -> None:
    """Línea entre centroide del departamento de los HECHOS y de la UNIDAD que tramita, ancho y
    opacidad proporcionales a `n_registros` de `matriz_origen_destino` (ya calculada, no se
    repite el SQL). `umbral_minimo_flujo` descarta flujos de un solo registro por legibilidad —
    sigue contado en la matriz/tabla, solo no se dibuja.
    """
    flujos = matriz_origen_destino(conexion)
    geo = gpd.read_file(RUTA_CARTOGRAFIA_DEPARTAMENTOS)
    centroides = dict(zip(geo["divipola_dep"], geo.geometry.centroid, strict=True))

    fig, ax = plt.subplots(figsize=(8, 10))
    geo.plot(ax=ax, color="#f0f0f0", edgecolor="grey", linewidth=0.2)

    max_n = flujos["n_registros"].max() if flujos.height else 1
    for fila in flujos.iter_rows(named=True):
        origen = centroides.get(fila["cod_dpto_hechos"])
        destino = centroides.get(fila["cod_dpto_unidad"])
        if origen is None or destino is None or fila["n_registros"] < umbral_minimo_flujo:
            continue
        peso = fila["n_registros"] / max_n
        ax.plot(
            [origen.x, destino.x], [origen.y, destino.y],
            color="crimson", linewidth=0.5 + 4 * peso, alpha=0.2 + 0.6 * peso,
        )

    ax.set_title(
        f"Flujos hechos → unidad que tramita\n{NOTA_ACTIVIDAD_REGISTRADA}", fontsize=10
    )
    ax.axis("off")
    fig.tight_layout()
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_salida, dpi=120)
    plt.close(fig)
