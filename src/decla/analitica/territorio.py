"""Territorio avanzado (plan_trabajo.md §8.2): perfiles territoriales, predominio con prueba
frente al segundo, autocorrelación espacial (Moran I / LISA) y análisis de puntos filtrado por
calidad de coordenada. Todo a partir de `fenomenos.asignacion_fenomeno` (Bloque 3A) unido a
`plata.registros_limpios` vía `texto.relato_procesado.caso_notica` (mismo join que usa
`decla.fenomenos.orquestador`).

Moran/LISA solo se calculan si hay cobertura suficiente (plan §8.2: "solo con cobertura
geográfica suficiente") — con ~346 relatos en 4 fenómenos repartidos en departamentos/municipios,
la mayoría de unidades tendrá conteo 0 o muy bajo; en vez de forzar un número sin sentido
estadístico, se devuelve explícitamente "insuficiente cobertura" cuando no se cumplen los
umbrales mínimos documentados abajo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import binomtest
from statsmodels.stats.proportion import proportion_confint

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CARTOGRAFIA_DEPARTAMENTOS = (
    RAIZ_PROYECTO / "data" / "referencia" / "cartografia" / "departamentos.geojson"
)
RUTA_CARTOGRAFIA_MUNICIPIOS = (
    RAIZ_PROYECTO / "data" / "referencia" / "cartografia" / "municipios.geojson"
)

# Umbrales de cobertura para Moran/LISA (decisión documentada, no silenciosa): por debajo de
# esto, el estadístico es ruido (demasiadas unidades en 0). Calibrados por orden de magnitud
# frente al tamaño real del dataset (~346 relatos, ~33 departamentos, 1122 municipios), no con
# una prueba formal de potencia — se revisan si el volumen de datos cambia mucho.
MORAN_MIN_UNIDADES_CON_DATOS_DEPARTAMENTO = 10
MORAN_MIN_PROMEDIO_POR_UNIDAD_DEPARTAMENTO = 2.0
MORAN_MIN_UNIDADES_CON_DATOS_MUNICIPIO = 30
MORAN_MIN_PROMEDIO_POR_UNIDAD_MUNICIPIO = 2.0

TAMANIO_MINIMO_PREDOMINIO = 5


def _asignacion_con_territorio(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT a.codigo_fenomeno, r.cod_dpto_hechos, r.cod_mpio_hechos,
               r.lat_hechos, r.long_hechos, r.calidad_coord_hechos
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        """
    ).pl()


# --- Perfiles territoriales (distancia de Hellinger + agrupamiento) -----------------------


def matriz_perfil_territorial(
    conexion: duckdb.DuckDBPyConnection, columna_territorio: str = "cod_dpto_hechos"
) -> pl.DataFrame:
    """Una fila por territorio, una columna por fenómeno, valores = proporción dentro del
    territorio (no conteo): es el "perfil" que compara composición, no volumen.
    """
    base = _asignacion_con_territorio(conexion).filter(pl.col(columna_territorio).is_not_null())
    conteo = base.group_by([columna_territorio, "codigo_fenomeno"]).agg(pl.len().alias("n"))
    pivote = conteo.pivot(values="n", index=columna_territorio, on="codigo_fenomeno").fill_null(0)
    columnas_fenomeno = [c for c in pivote.columns if c != columna_territorio]
    totales = pivote.select(columnas_fenomeno).sum_horizontal()
    return pivote.with_columns(
        [(pl.col(c) / totales).alias(c) for c in columnas_fenomeno]
    ).filter(totales > 0)


def distancia_hellinger(p: np.ndarray, q: np.ndarray) -> float:
    """H(p,q) = sqrt(0.5 * sum((sqrt(p_i) - sqrt(q_i))^2)); rango [0,1], 0 = perfiles idénticos."""
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)))


def matriz_distancia_hellinger(
    perfil: pl.DataFrame, columna_territorio: str
) -> tuple[list[str], np.ndarray]:
    territorios = perfil[columna_territorio].to_list()
    valores = perfil.drop(columna_territorio).to_numpy()
    n = len(territorios)
    distancias = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = distancia_hellinger(valores[i], valores[j])
            distancias[i, j] = distancias[j, i] = d
    return territorios, distancias


def agrupar_perfiles_territoriales(
    territorios: list[str], distancias: np.ndarray, n_grupos: int
) -> dict[str, int]:
    """Agrupamiento jerárquico (`linkage` promedio) sobre la matriz de Hellinger, cortado en
    `n_grupos`. `n_grupos` es una decisión del analista (cuántos "perfiles territoriales"
    distintos quiere ver), no algo que el código adivine; se expone como parámetro explícito.
    """
    if len(territorios) < 2:
        return {t: 0 for t in territorios}
    condensada = squareform(distancias, checks=False)
    enlace = linkage(condensada, method="average")
    etiquetas = fcluster(enlace, t=min(n_grupos, len(territorios)), criterion="maxclust")
    return dict(zip(territorios, etiquetas.tolist(), strict=True))


# --- Predominio con prueba frente al segundo ------------------------------------------------


def predominio_territorial(
    conexion: duckdb.DuckDBPyConnection,
    columna_territorio: str = "cod_dpto_hechos",
    tamanio_minimo: int = TAMANIO_MINIMO_PREDOMINIO,
) -> pl.DataFrame:
    """Fenómeno predominante por territorio, con prueba binomial de que supera al segundo
    (H0: entre el primero y el segundo son igual de frecuentes, excluyendo los demás) y filtro de
    tamaño mínimo (plan §8.2). No aplica contracción bayesiana hacia la media departamental para
    municipios pequeños (simplificación deliberada: con ~346 relatos la mayoría de municipios ya
    queda fuera por `tamanio_minimo`, que es la misma protección en la práctica).
    """
    base = _asignacion_con_territorio(conexion).filter(pl.col(columna_territorio).is_not_null())
    conteo = base.group_by([columna_territorio, "codigo_fenomeno"]).agg(pl.len().alias("n"))

    filas: list[dict[str, Any]] = []
    for (territorio,), grupo in conteo.group_by([columna_territorio]):
        grupo = grupo.sort("n", descending=True)
        n_total = int(grupo["n"].sum())
        fila: dict[str, Any] = {
            columna_territorio: territorio,
            "n_total": n_total,
            "cumple_tamanio_minimo": n_total >= tamanio_minimo,
        }
        if n_total < tamanio_minimo:
            filas.append(fila)
            continue

        top = grupo.row(0, named=True)
        n_top = int(top["n"])
        segundo = grupo.row(1, named=True) if grupo.height > 1 else None
        n_segundo = int(segundo["n"]) if segundo else 0

        fila["fenomeno_predominante"] = top["codigo_fenomeno"]
        fila["n_predominante"] = n_top
        fila["pct_predominante"] = round(n_top * 100.0 / n_total, 2)
        fila["fenomeno_segundo"] = segundo["codigo_fenomeno"] if segundo else None
        fila["n_segundo"] = n_segundo

        if n_segundo == 0:
            fila["p_valor_supera_segundo"] = 0.0  # único fenómeno presente: predominio trivial
        else:
            prueba = binomtest(n_top, n_top + n_segundo, p=0.5, alternative="greater")
            fila["p_valor_supera_segundo"] = round(prueba.pvalue, 4)
        filas.append(fila)
    return pl.DataFrame(filas)


def intervalo_confianza_participacion(n_exitos: int, n_total: int) -> tuple[float, float]:
    """IC 95 % Wilson para la participación de un fenómeno dentro de un territorio."""
    bajo, alto = proportion_confint(n_exitos, n_total, alpha=0.05, method="wilson")
    return round(float(bajo), 4), round(float(alto), 4)


# --- Autocorrelación espacial (Moran I / LISA) ----------------------------------------------


def _pesos_espaciales(ruta_geojson: Path, columna_codigo: str) -> Any:
    import geopandas as gpd
    from libpysal.weights import Queen

    gdf = gpd.read_file(ruta_geojson)
    return Queen.from_dataframe(gdf, ids=gdf[columna_codigo].tolist(), use_index=False)


def _verificar_cobertura(
    conteos: dict[str, int], minimo_unidades: int, minimo_promedio: float
) -> tuple[bool, dict[str, Any]]:
    valores = [n for n in conteos.values() if n > 0]
    n_unidades_con_datos = len(valores)
    promedio = sum(valores) / n_unidades_con_datos if n_unidades_con_datos else 0.0
    cumple = n_unidades_con_datos >= minimo_unidades and promedio >= minimo_promedio
    return cumple, {
        "n_unidades_con_datos": n_unidades_con_datos,
        "promedio_por_unidad": round(promedio, 2),
    }


def calcular_moran(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    nivel: str = "departamento",
    permutaciones: int = 999,
) -> dict[str, Any]:
    """Moran I global para un fenómeno, a nivel 'departamento' o 'municipio'. Devuelve
    `{"calculado": False, "motivo": ..., ...diagnóstico de cobertura}` si no hay suficiente
    cobertura — nunca un número sin respaldo estadístico (plan §8.2, "decide con datos").
    """
    import esda

    if nivel == "departamento":
        ruta, columna_cartografia, columna_registros = (
            RUTA_CARTOGRAFIA_DEPARTAMENTOS,
            "divipola_dep",
            "cod_dpto_hechos",
        )
        minimo_unidades, minimo_promedio = (
            MORAN_MIN_UNIDADES_CON_DATOS_DEPARTAMENTO,
            MORAN_MIN_PROMEDIO_POR_UNIDAD_DEPARTAMENTO,
        )
    elif nivel == "municipio":
        ruta, columna_cartografia, columna_registros = (
            RUTA_CARTOGRAFIA_MUNICIPIOS,
            "divipola_mun",
            "cod_mpio_hechos",
        )
        minimo_unidades, minimo_promedio = (
            MORAN_MIN_UNIDADES_CON_DATOS_MUNICIPIO,
            MORAN_MIN_PROMEDIO_POR_UNIDAD_MUNICIPIO,
        )
    else:
        raise ValueError(f"nivel debe ser 'departamento' o 'municipio', no {nivel!r}")

    base = _asignacion_con_territorio(conexion).filter(
        (pl.col("codigo_fenomeno") == codigo_fenomeno) & pl.col(columna_registros).is_not_null()
    )
    conteo_por_unidad = dict(
        zip(
            base[columna_registros].to_list(),
            [1] * base.height,
            strict=True,
        )
    )
    # Reconteo real (el zip de arriba solo fija claves; agregamos de verdad abajo).
    conteo_por_unidad = (
        base.group_by(columna_registros)
        .agg(pl.len().alias("n"))
        .to_pandas()
        .set_index(columna_registros)["n"]
        .to_dict()
    )

    cumple, diagnostico = _verificar_cobertura(conteo_por_unidad, minimo_unidades, minimo_promedio)
    if not cumple:
        return {"calculado": False, "motivo": "cobertura insuficiente", **diagnostico}

    pesos = _pesos_espaciales(ruta, columna_cartografia)
    y = np.array([conteo_por_unidad.get(unidad, 0) for unidad in pesos.id_order], dtype=float)
    moran = esda.Moran(y, pesos, permutations=permutaciones)
    return {
        "calculado": True,
        "I": round(float(moran.I), 4),
        "p_sim": round(float(moran.p_sim), 4),
        "n_unidades": len(pesos.id_order),
        **diagnostico,
    }


def calcular_lisa(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    nivel: str = "departamento",
    permutaciones: int = 999,
) -> dict[str, Any]:
    """LISA (Moran local) por unidad. Mismo gate de cobertura que `calcular_moran`; si no se
    calcula, devuelve el mismo diagnóstico sin tabla de resultados.
    """
    import esda

    if nivel == "departamento":
        ruta, columna_cartografia, columna_registros = (
            RUTA_CARTOGRAFIA_DEPARTAMENTOS,
            "divipola_dep",
            "cod_dpto_hechos",
        )
        minimo_unidades, minimo_promedio = (
            MORAN_MIN_UNIDADES_CON_DATOS_DEPARTAMENTO,
            MORAN_MIN_PROMEDIO_POR_UNIDAD_DEPARTAMENTO,
        )
    elif nivel == "municipio":
        ruta, columna_cartografia, columna_registros = (
            RUTA_CARTOGRAFIA_MUNICIPIOS,
            "divipola_mun",
            "cod_mpio_hechos",
        )
        minimo_unidades, minimo_promedio = (
            MORAN_MIN_UNIDADES_CON_DATOS_MUNICIPIO,
            MORAN_MIN_PROMEDIO_POR_UNIDAD_MUNICIPIO,
        )
    else:
        raise ValueError(f"nivel debe ser 'departamento' o 'municipio', no {nivel!r}")

    base = _asignacion_con_territorio(conexion).filter(
        (pl.col("codigo_fenomeno") == codigo_fenomeno) & pl.col(columna_registros).is_not_null()
    )
    conteo_por_unidad = (
        base.group_by(columna_registros)
        .agg(pl.len().alias("n"))
        .to_pandas()
        .set_index(columna_registros)["n"]
        .to_dict()
    )
    cumple, diagnostico = _verificar_cobertura(conteo_por_unidad, minimo_unidades, minimo_promedio)
    if not cumple:
        return {"calculado": False, "motivo": "cobertura insuficiente", **diagnostico}

    pesos = _pesos_espaciales(ruta, columna_cartografia)
    unidades = list(pesos.id_order)
    y = np.array([conteo_por_unidad.get(unidad, 0) for unidad in unidades], dtype=float)
    lisa = esda.Moran_Local(y, pesos, permutations=permutaciones)
    tabla = pl.DataFrame(
        {
            "unidad": unidades,
            "I_local": lisa.Is.tolist(),
            "p_sim": lisa.p_sim.tolist(),
            "cuadrante": lisa.q.tolist(),
        }
    )
    return {"calculado": True, "tabla": tabla, **diagnostico}


# --- Análisis de puntos (solo coordenadas validadas) ----------------------------------------


def resumen_calidad_puntos(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT calidad_coord_hechos, count(*) AS n,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM plata.registros_limpios
        GROUP BY calidad_coord_hechos
        ORDER BY n DESC
        """
    ).pl()


def dispersion_puntos_por_fenomeno(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Centroide y dispersión (desviación estándar de la distancia al centroide, en grados) de
    los puntos `calidad_coord_hechos='exacta'` de cada fenómeno. No se analiza más fino que esta
    calidad (CLAUDE.md §4.17: precisión efectiva ~100 m, no tiene sentido ir más allá).
    """
    base = _asignacion_con_territorio(conexion).filter(
        (pl.col("calidad_coord_hechos") == "exacta")
        & pl.col("lat_hechos").is_not_null()
        & pl.col("long_hechos").is_not_null()
    )
    filas: list[dict[str, Any]] = []
    for (codigo,), grupo in base.group_by(["codigo_fenomeno"]):
        lat = grupo["lat_hechos"].to_numpy()
        long = grupo["long_hechos"].to_numpy()
        centroide_lat, centroide_long = float(lat.mean()), float(long.mean())
        distancias = np.sqrt((lat - centroide_lat) ** 2 + (long - centroide_long) ** 2)
        filas.append(
            {
                "codigo_fenomeno": codigo,
                "n_puntos_validos": len(lat),
                "centroide_lat": round(centroide_lat, 4),
                "centroide_long": round(centroide_long, 4),
                "dispersion_grados": round(float(distancias.std()), 4),
            }
        )
    return pl.DataFrame(filas)
