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
        suffix="_anio_anterior",
    ).drop(["_anio_anterior_de", "mes_anio_anterior"])
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


def ind_fenomenos(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Noticias por fenómeno (plan_trabajo.md §8.1, familia "Fenómenos") y % no clasificado.

    `fenomenos.asignacion_fenomeno` (construida por `decla.fenomenos.asignacion` a partir de la
    taxonomía v1.0 congelada) puede asignar un mismo relato a más de un código: dos de los cuatro
    fenómenos vienen de la partición de HDBSCAN y los otros de la de NMF (dos particiones
    distintas del mismo corpus, ver docstring de `asignacion.py`). Por eso `pct_participacion` se
    calcula contra el total de relatos procesados, no contra la suma de los `n_noticias` de cada
    fenómeno: esa suma puede superar el 100 %, y eso es esperado, no un error de conteo.

    "Conteo ajustado" (plan §7.4, suma de probabilidades) no se reporta aparte todavía: las filas
    de clustering siguen con `probabilidad=1.0`, pero desde ADR 0025 puede haber también filas
    promovidas del clasificador (`make promover-clasificador-fenomenos`) con probabilidad real —
    si conviven ambos métodos para un mismo código, `n_noticias` ya no es exactamente la suma de
    probabilidades. Calcular el conteo ajustado queda pendiente de esa pieza.
    """
    return conexion.sql(
        """
        WITH total AS (SELECT count(*) AS n FROM texto.relato_procesado)
        SELECT a.codigo_fenomeno, count(*) AS n_noticias,
               round(count(*) * 100.0 / total.n, 2) AS pct_participacion
        FROM fenomenos.asignacion_fenomeno a, total
        GROUP BY a.codigo_fenomeno, total.n
        UNION ALL
        SELECT '(no_clasificado)' AS codigo_fenomeno, count(*) AS n_noticias,
               round(count(*) * 100.0 / (SELECT n FROM total), 2) AS pct_participacion
        FROM texto.relato_procesado r, total
        WHERE NOT EXISTS (
            SELECT 1 FROM fenomenos.asignacion_fenomeno a WHERE a.registro_uid = r.registro_uid
        )
        GROUP BY total.n
        ORDER BY n_noticias DESC
        """
    ).pl()


def ind_delito_dentro_de_fenomeno(
    conexion: duckdb.DuckDBPyConnection, codigo_fenomeno: str
) -> pl.DataFrame:
    """Composición por delito tipificado (y artículo) **dentro de un fenómeno específico**.

    Responde "¿qué tipo de lavado es?" cuando el fenómeno en sí (p. ej. `lavado_de_activos`, el
    clúster más grande y menos diferenciado de la taxonomía v1.0 — ADR 0014: tres métodos de
    agrupamiento distintos convergieron en el mismo grupo genérico) no distingue modalidades por
    sí solo. Usa `delito_nombre`/`articulo_cp` (campo estructurado ya extraído y aprobado, no una
    nueva categoría inventada) como proxy legible de la modalidad.
    """
    return conexion.sql(
        """
        SELECT
            coalesce(r.delito_nombre, '(no parseable)') AS delito_nombre, r.articulo_cp,
            count(*) AS n,
            round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE a.codigo_fenomeno = ?
        GROUP BY r.delito_nombre, r.articulo_cp
        ORDER BY n DESC
        """,
        params=[codigo_fenomeno],
    ).pl()


def ind_sector_dentro_de_fenomeno(
    conexion: duckdb.DuckDBPyConnection, codigo_fenomeno: str
) -> pl.DataFrame:
    """Sector económico mencionado **dentro de un fenómeno específico** (mismo propósito que
    `ind_delito_dentro_de_fenomeno`: diferenciar modalidades dentro de un fenómeno demasiado
    amplio). A diferencia de `ind_sectores` (que agrupa por *origen* del dato: explícito/inferido/
    indeterminado para no forzar una etiqueta), aquí se muestra el **valor** del sector cuando es
    explícito o inferido de alta confianza, porque lo que se busca es la modalidad, no el origen.
    """
    return conexion.sql(
        """
        WITH base AS (
            SELECT
                CASE
                    WHEN m.origen = 'explicito_regla' THEN m.valor_normalizado
                    WHEN m.origen = 'inferido_modelo' AND m.valor_normalizado IS NOT NULL
                         AND m.valor_normalizado != 'indeterminado' THEN m.valor_normalizado
                    ELSE 'indeterminado'
                END AS sector
            FROM fenomenos.asignacion_fenomeno a
            JOIN texto.menciones m ON m.registro_uid = a.registro_uid
            WHERE a.codigo_fenomeno = ? AND m.categoria = 'sector' AND m.polaridad = 'afirmada'
        )
        SELECT sector, count(*) AS n,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM base
        GROUP BY sector
        ORDER BY n DESC
        """,
        params=[codigo_fenomeno],
    ).pl()


def ind_sectores(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Sector explícito / inferido de alta confianza / indeterminado, **en columnas separadas**
    (plan_trabajo.md §6.4, §8.1: "no forzar una etiqueta"; CLAUDE.md §2.3). Excluye menciones
    negadas o hipotéticas por defecto; hoy `decla.conocimiento.orquestador` siempre escribe la
    mención de sector con `polaridad='afirmada'`, así que el filtro es una garantía explícita
    (CLAUDE.md), no un no-op invisible, por si en el futuro se detecta negación de sector.

    Denominador: relatos con una mención de sector (`texto.menciones` solo escribe esa fila si el
    relato tiene texto no vacío); no es el total de relatos en alcance si alguno quedó sin texto.
    """
    return conexion.sql(
        """
        WITH base AS (
            SELECT
                CASE
                    WHEN origen = 'explicito_regla' THEN 'explicito'
                    WHEN origen = 'inferido_modelo' AND valor_normalizado IS NOT NULL
                         AND valor_normalizado != 'indeterminado' THEN 'inferido_alta_confianza'
                    ELSE 'indeterminado'
                END AS categoria_sector
            FROM texto.menciones
            WHERE categoria = 'sector' AND polaridad = 'afirmada'
        )
        SELECT categoria_sector, count(*) AS n,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM base
        GROUP BY categoria_sector
        ORDER BY n DESC
        """
    ).pl()


def ind_mecanismo(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Mecanismo (modus operandi) detectado por similitud zero-shot contra las 12 definiciones
    semilla de `config/categorias_menciones.yaml` (`decla.conocimiento.zero_shot`): compra de
    ganado, minería ilegal de oro, empresas fachada, testaferros, criptoactivos, captación
    ilegal, etc. — ya se calculaba en `make conocimiento` (plan §6.2) pero nunca se mostró en la
    app. Responde directamente "qué tipo de lavado" en vez de repetir el fenómeno amplio. Por
    debajo del umbral de confianza (`config/umbrales.yaml`, `zero_shot_mecanismo`) queda
    `no_clasificado`, un resultado legítimo, no un error.
    """
    return conexion.sql(
        """
        SELECT coalesce(valor_normalizado, 'no_clasificado') AS mecanismo, count(*) AS n,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM texto.menciones
        WHERE categoria = 'mecanismo' AND polaridad = 'afirmada'
        GROUP BY mecanismo
        ORDER BY n DESC
        """
    ).pl()


def ind_mecanismo_dentro_de_fenomeno(
    conexion: duckdb.DuckDBPyConnection, codigo_fenomeno: str
) -> pl.DataFrame:
    """Igual que `ind_mecanismo`, pero **dentro de un fenómeno específico** (mismo propósito que
    `ind_delito_dentro_de_fenomeno`/`ind_sector_dentro_de_fenomeno`: diferenciar modalidades
    dentro de un fenómeno demasiado amplio, sin reabrir el clustering).
    """
    return conexion.sql(
        """
        SELECT coalesce(m.valor_normalizado, 'no_clasificado') AS mecanismo, count(*) AS n,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.menciones m ON m.registro_uid = a.registro_uid
        WHERE a.codigo_fenomeno = ? AND m.categoria = 'mecanismo' AND m.polaridad = 'afirmada'
        GROUP BY mecanismo
        ORDER BY n DESC
        """,
        params=[codigo_fenomeno],
    ).pl()


def ranking_tendencia_delito(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Ranking de qué combinación delito×territorio se aleja más del pronóstico ingenuo (repetir
    el último valor observado) en `oro.pronosticos_delito` (`make prediccion`, ADR 2026-11-06).

    Responde "¿qué tipo de delito está en tendencia?" en vez de "¿qué fenómeno está en
    tendencia?" (que siempre es `lavado_de_activos`, el único alcance del dataset — mismo motivo
    que `ind_delito_dentro_de_fenomeno`). Solo reporta una serie si algún método con tendencia
    superó al ingenuo en el backtest (`supera_ingenuo`): sin eso, no hay evidencia de tendencia
    real distinta del ruido, y no se reporta nada (CLAUDE.md, "no inventes cifras").
    """
    try:
        pronosticos = conexion.sql("SELECT * FROM oro.pronosticos_delito").pl()
    except duckdb.CatalogException:
        return pl.DataFrame()  # `make prediccion` todavía no corrió.
    if pronosticos.height == 0:
        return pl.DataFrame()

    ultimo_horizonte = pronosticos.group_by(["delito_nombre", "territorio"]).agg(
        pl.col("periodo_pronosticado").max().alias("periodo_pronosticado")
    )
    en_ultimo_horizonte = pronosticos.join(
        ultimo_horizonte, on=["delito_nombre", "territorio", "periodo_pronosticado"]
    )

    base_ingenuo = en_ultimo_horizonte.filter(pl.col("metodo") == "ingenuo").select(
        "delito_nombre", "territorio", pl.col("valor_punto").alias("valor_ingenuo")
    )
    con_tendencia = en_ultimo_horizonte.filter(
        (pl.col("metodo") != "ingenuo") & pl.col("supera_ingenuo").fill_null(False)
    )
    if con_tendencia.height == 0:
        return pl.DataFrame()

    combinado = con_tendencia.join(base_ingenuo, on=["delito_nombre", "territorio"], how="inner")
    combinado = combinado.with_columns(
        (
            (pl.col("valor_punto") - pl.col("valor_ingenuo"))
            * 100
            / pl.when(pl.col("valor_ingenuo") > 0).then(pl.col("valor_ingenuo")).otherwise(1.0)
        )
        .round(2)
        .alias("variacion_pct_vs_ingenuo")
    )
    # Si más de un método superó el ingenuo para la misma serie, prioriza el de menor error de
    # backtest (MASE) en vez de promediar métodos con calidad distinta.
    combinado = combinado.sort("mase_backtest").unique(
        subset=["delito_nombre", "territorio"], keep="first"
    )
    return combinado.select(
        "delito_nombre",
        "territorio",
        "metodo",
        "valor_punto",
        "valor_ingenuo",
        "variacion_pct_vs_ingenuo",
        "mase_backtest",
        "wape_backtest",
    ).sort("variacion_pct_vs_ingenuo", descending=True)
