"""Clasificación final de calidad de coordenadas (CLAUDE.md §4.17; Fase 3.3).

Reusa `decla.calidad.coordenadas.reparar_coordenadas` (I0: reescalado, inversión, caja de
Colombia) y añade la validación punto-en-polígono contra la cartografía real
(`data/referencia/cartografia/municipios.geojson`), que I0 no tenía todavía.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from decla.calidad.coordenadas import reparar_coordenadas

_MAPA_METODO_A_CALIDAD = {
    "vacia": "faltante",
    "reparada_escala": "reparada_decimal",
    "invertida": "invertida_corregida",
    "fuera_de_caja": "fuera_pais",
    "no_reparable": "faltante",
}


def cargar_geometrias_municipios(ruta_geojson: Path) -> dict[str, BaseGeometry]:
    import geopandas as gpd

    gdf = gpd.read_file(ruta_geojson)
    return dict(zip(gdf["divipola_mun"], gdf["geometry"], strict=True))


@dataclass
class ResultadoCoordenadaFinal:
    lat: float | None
    long: float | None
    calidad_coord: str


def clasificar_coordenada(
    lat_texto: str | None,
    long_texto: str | None,
    cod_mpio_declarado: str | None,
    centroide: tuple[float, float] | None,
    geometrias_por_mpio: dict[str, BaseGeometry],
) -> ResultadoCoordenadaFinal:
    base = reparar_coordenadas(lat_texto, long_texto, centroide)

    if base.metodo != "correcta":
        calidad = _MAPA_METODO_A_CALIDAD.get(base.metodo, "faltante")
        return ResultadoCoordenadaFinal(
            lat=base.lat_reparada, long=base.long_reparada, calidad_coord=calidad
        )

    if base.coincide_centroide:
        calidad = "centroide"
    elif cod_mpio_declarado and cod_mpio_declarado in geometrias_por_mpio:
        assert base.lat_reparada is not None and base.long_reparada is not None
        punto = Point(base.long_reparada, base.lat_reparada)
        geometria = geometrias_por_mpio[cod_mpio_declarado]
        calidad = "exacta" if geometria.contains(punto) else "fuera_municipio"
    else:
        calidad = "exacta"

    return ResultadoCoordenadaFinal(
        lat=base.lat_reparada, long=base.long_reparada, calidad_coord=calidad
    )
