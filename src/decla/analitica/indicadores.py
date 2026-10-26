"""Indicadores descriptivos (plan_trabajo.md §8.1, Fase 7 parcial — sin NLP).

Cada función tiene su ficha en `docs/fichas/indicadores/` (unidad, fecha de referencia,
numerador, denominador, limitaciones). Si falta una referencia (población), el indicador que la
necesita queda `None`: nunca se inventa un denominador (CLAUDE.md, "no hagas" de I1).
"""

from __future__ import annotations

import duckdb
import polars as pl


def _contar(conexion: duckdb.DuckDBPyConnection, tabla_calificada: str) -> int:
    resultado = conexion.sql(f"SELECT count(*) AS n FROM {tabla_calificada}").pl()["n"].item()
    return int(resultado)


def ind_volumen(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    n_registros = _contar(conexion, "plata.registros_limpios")
    n_noticias = _contar(conexion, "entidades.noticia_criminal")
    n_casos = _contar(conexion, "entidades.caso")
    razon = round(n_registros / n_noticias, 4) if n_noticias else None
    return pl.DataFrame(
        [
            {
                "n_registros": n_registros,
                "n_noticias": n_noticias,
                "n_casos": n_casos,
                "razon_registros_noticia": razon,
            }
        ]
    )


def ind_composicion_delito(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT
            coalesce(delito_nombre, '(no parseable)') AS delito_nombre,
            articulo_cp,
            count(*) AS n,
            round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM plata.registros_limpios
        GROUP BY delito_nombre, articulo_cp
        ORDER BY n DESC
        """
    ).pl()


def ind_composicion_estado_etapa(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT estado_norm, etapa_norm, count(*) AS n,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM plata.registros_limpios
        GROUP BY estado_norm, etapa_norm
        ORDER BY n DESC
        """
    ).pl()


def ind_territorio_conteo(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT cod_dpto_hechos, cod_mpio_hechos, anio_iso_creacion AS anio, count(*) AS n_registros
        FROM plata.registros_limpios
        WHERE cod_mpio_hechos IS NOT NULL
        GROUP BY cod_dpto_hechos, cod_mpio_hechos, anio_iso_creacion
        ORDER BY cod_dpto_hechos, cod_mpio_hechos, anio
        """
    ).pl()


def ind_territorio_cociente_localizacion(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        WITH por_mpio_delito AS (
            SELECT cod_mpio_hechos AS cod_mpio, delito_nombre, count(*) AS n
            FROM plata.registros_limpios
            WHERE cod_mpio_hechos IS NOT NULL AND delito_nombre IS NOT NULL
            GROUP BY cod_mpio_hechos, delito_nombre
        ),
        por_mpio AS (
            SELECT cod_mpio, sum(n) AS n_total_mpio FROM por_mpio_delito GROUP BY cod_mpio
        ),
        por_delito_nacional AS (
            SELECT delito_nombre, sum(n) AS n_nacional FROM por_mpio_delito GROUP BY delito_nombre
        ),
        total_nacional AS (SELECT sum(n) AS n_total_nacional FROM por_mpio_delito)
        SELECT
            pmd.cod_mpio, pmd.delito_nombre, pmd.n, pm.n_total_mpio,
            pdn.n_nacional, tn.n_total_nacional,
            round(
                (pmd.n * 1.0 / pm.n_total_mpio) / (pdn.n_nacional * 1.0 / tn.n_total_nacional), 4
            ) AS cociente_localizacion
        FROM por_mpio_delito pmd
        JOIN por_mpio pm ON pmd.cod_mpio = pm.cod_mpio
        JOIN por_delito_nacional pdn ON pmd.delito_nombre = pdn.delito_nombre
        CROSS JOIN total_nacional tn
        ORDER BY cociente_localizacion DESC
        """
    ).pl()


def suavizar_tasa_bayesiano_empirico(
    n_eventos: int,
    poblacion: float | None,
    tasa_referencia: float | None,
    peso_prior: float = 10_000.0,
) -> float | None:
    """Contrae la tasa municipal hacia `tasa_referencia` (la departamental) cuando la población
    es pequeña frente a `peso_prior` (plan_trabajo.md §8.2): tasa = (n_eventos +
    peso_prior·tasa_referencia) / (población + peso_prior). `peso_prior` está en las mismas
    unidades que `poblacion` (personas), no en registros.
    """
    if poblacion is None or poblacion <= 0 or tasa_referencia is None:
        return None
    return (n_eventos + peso_prior * tasa_referencia) / (poblacion + peso_prior)


def ind_territorio_tasa(
    conexion: duckdb.DuckDBPyConnection, peso_prior: float = 10_000.0
) -> pl.DataFrame:
    """Tasa por 100.000 hab. con `plata.dim_territorio` (DANE); si no hay población para ese
    municipio/año queda `None` (pendiente de referencia). Incluye la versión suavizada hacia la
    tasa departamental (plan_trabajo.md §8.2).
    """
    df = conexion.sql(
        """
        SELECT
            r.cod_dpto_hechos AS cod_dpto, r.cod_mpio_hechos AS cod_mpio,
            r.anio_iso_creacion AS anio, count(*) AS n_registros,
            max(dt.poblacion_total) AS poblacion_total
        FROM plata.registros_limpios r
        LEFT JOIN plata.dim_territorio dt
            ON r.cod_mpio_hechos = dt.cod_mpio AND r.anio_iso_creacion = dt.anio
        WHERE r.cod_mpio_hechos IS NOT NULL
        GROUP BY r.cod_dpto_hechos, r.cod_mpio_hechos, r.anio_iso_creacion
        """
    ).pl()

    df = df.with_columns(
        (pl.col("n_registros") / pl.col("poblacion_total") * 100_000).alias("tasa_por_100k")
    )

    tasas_dpto = (
        df.filter(pl.col("poblacion_total").is_not_null())
        .group_by(["cod_dpto", "anio"])
        .agg((pl.col("n_registros").sum() / pl.col("poblacion_total").sum()).alias("tasa_dpto"))
    )
    df = df.join(tasas_dpto, on=["cod_dpto", "anio"], how="left")

    tasas_suavizadas: list[float | None] = []
    for fila in df.to_dicts():
        tasa_suavizada = suavizar_tasa_bayesiano_empirico(
            fila["n_registros"], fila["poblacion_total"], fila["tasa_dpto"], peso_prior
        )
        tasas_suavizadas.append(tasa_suavizada * 100_000 if tasa_suavizada is not None else None)

    return df.with_columns(pl.Series("tasa_suavizada_por_100k", tasas_suavizadas)).drop("tasa_dpto")


def ind_tiempo_mensual(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    df = conexion.sql(
        """
        SELECT anio_iso_creacion AS anio, mes_creacion AS mes, count(*) AS n_registros
        FROM plata.registros_limpios
        WHERE fecha_creacion_valida
        GROUP BY anio_iso_creacion, mes_creacion
        ORDER BY anio, mes
        """
    ).pl()
    previo = df.select(
        pl.col("anio").alias("_anio_anterior_de"),
        pl.col("mes"),
        pl.col("n_registros").alias("n_registros_anio_anterior"),
    )
    df = df.join(
        previo,
        left_on=[(pl.col("anio") - 1), pl.col("mes")],
        right_on=["_anio_anterior_de", "mes"],
        how="left",
    )
    return df.with_columns(
        (
            (pl.col("n_registros") - pl.col("n_registros_anio_anterior"))
            / pl.col("n_registros_anio_anterior")
            * 100
        )
        .round(2)
        .alias("variacion_interanual_pct")
    )


def ind_rezagos(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT
            median(dias_hecho_denuncia) AS mediana_dias_hecho_denuncia,
            median(dias_denuncia_creacion) AS mediana_dias_denuncia_creacion,
            median(dias_creacion_asignacion) AS mediana_dias_creacion_asignacion
        FROM plata.registros_limpios
        """
    ).pl()


def ind_procesales(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """% con `CASO_FECHA_PRESCRIPCION` declarada a menos de 365 días de hoy. Usa el valor que el
    sistema declaró, no una regla fija (ADR 0008: "hecho + 20 años" no se sostiene en los datos
    reales).
    """
    return conexion.sql(
        """
        SELECT
            etapa_norm,
            count(*) AS n,
            sum(
                CASE WHEN fecha_prescripcion_declarada IS NOT NULL
                     AND (fecha_prescripcion_declarada - current_date) BETWEEN 0 AND 365
                THEN 1 ELSE 0 END
            ) AS n_cerca_prescripcion_declarada
        FROM plata.registros_limpios
        GROUP BY etapa_norm
        ORDER BY n DESC
        """
    ).pl()


def ind_conexidad(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql(
        """
        SELECT
            count(*) AS n_noticias,
            sum(CASE WHEN tiene_conexos_declarados THEN 1 ELSE 0 END) AS n_con_conexos_declarados,
            round(
                sum(CASE WHEN tiene_conexos_declarados THEN 1 ELSE 0 END) * 100.0 / count(*), 2
            ) AS pct_con_conexos_declarados
        FROM entidades.grupo_conexo
        """
    ).pl()


def ind_calidad(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return conexion.sql("SELECT * FROM plata.reporte_calidad ORDER BY categoria, clave").pl()
