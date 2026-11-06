"""App Streamlit local de consulta (plan_trabajo.md Fase 11; I3, Bloque 3E).

**Sin autenticación ni roles** — decisión explícita de la persona (ADR 0015): hoy la herramienta
la usa una sola persona en su propia máquina, nada se expone a la web, y lo que importa es el
resultado analítico, no el control de acceso. Es una reducción de alcance frente a la Fase 11 del
plan (que pide 4 roles con streamlit-authenticator o proxy institucional).

Abre `data/warehouse.duckdb` en **solo lectura** (DuckDB admite un solo escritor,
`decla.comun.duckdb_io`): esta app nunca escribe. La cola de revisión de alertas de emergencia
(confirmar/descartar) queda fuera de esta ronda — necesitaría una conexión de escritura separada,
como ya hace `app_revision_fenomenos.py` para la taxonomía, y no es el foco actual (ver ADR 0015).

Uso: `uv run streamlit run src/decla/app/main.py` (o `make app`).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import polars as pl
import streamlit as st
import yaml

from decla.analitica import asociaciones as aso
from decla.analitica import indicadores as ind
from decla.analitica import territorio as terr
from decla.app.legibilidad import (
    agregar_nombres_fenomeno,
    agregar_nombres_territorio,
    decodificar_indice_periodo,
    divipola,
    etiqueta,
    glosario,
    grafico_barras,
    grafico_linea_pronostico,
    mostrar,
    traducir_itemsets_df,
    traducir_termino_formula,
)
from decla.comun.duckdb_io import conectar
from decla.emergencia.linea_base import construir_series_delito_territorio

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_TAXONOMIA = RAIZ_PROYECTO / "config" / "taxonomia" / "v1.0.yaml"
RAIZ_EMBEDDINGS = RAIZ_PROYECTO / "data" / "embeddings"

NOTA_ACTIVIDAD_REGISTRADA = "Actividad institucional registrada, no incidencia real del delito."

st.set_page_config(page_title="DECLA — Analítica de fenómenos", layout="wide")


@st.cache_resource
def _conexion() -> duckdb.DuckDBPyConnection:
    return conectar(RUTA_DUCKDB, solo_lectura=True)


@st.cache_data
def _cargar_taxonomia() -> dict:
    if not RUTA_TAXONOMIA.exists():
        return {"fenomenos": []}
    return yaml.safe_load(RUTA_TAXONOMIA.read_text(encoding="utf-8")) or {"fenomenos": []}


def _nota() -> None:
    st.caption(NOTA_ACTIVIDAD_REGISTRADA + " · Versión de taxonomía: v1.0")


def _codigos_fenomeno(conexion: duckdb.DuckDBPyConnection) -> list[str]:
    return sorted(
        conexion.sql("SELECT DISTINCT codigo_fenomeno FROM fenomenos.asignacion_fenomeno").pl()[
            "codigo_fenomeno"
        ].to_list()
    )


def pagina_indicadores() -> None:
    st.header("Indicadores")
    _nota()
    glosario()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()

    st.subheader("Volumen")
    mostrar(ind.ind_volumen(conexion))

    st.subheader("Fenómenos")
    st.caption(
        "Todos los casos de este sistema son, por alcance, de lavado de activos — por eso no "
        "sorprende que domine. Esta tabla no dice *si* hubo lavado, sino *qué modalidad* tomó "
        "(detectada por análisis de texto). Para el delito formal y sus delitos conexos "
        "(contrabando, narcotráfico, falsificación, etc.), ver 'Composición por delito' abajo."
    )
    fenomenos_df = ind.ind_fenomenos(conexion)
    mostrar(fenomenos_df, taxonomia=taxonomia)
    fenomenos_legible = agregar_nombres_fenomeno(fenomenos_df.to_pandas(), taxonomia)
    st.plotly_chart(
        grafico_barras(fenomenos_legible, "codigo_fenomeno", "n_noticias", "Noticias por fenómeno"),
        use_container_width=True,
    )

    st.subheader("Sectores económicos mencionados")
    sectores_df = ind.ind_sectores(conexion)
    mostrar(sectores_df)
    st.plotly_chart(
        grafico_barras(
            sectores_df.to_pandas(), "categoria_sector", "n", "Menciones por origen del dato"
        ),
        use_container_width=True,
    )

    st.subheader("Composición por delito")
    st.caption(
        "Tipificación penal formal registrada en el expediente: el delito de lavado de activos "
        "y los delitos conexos o fuente citados (enriquecimiento ilícito, falsificación de "
        "moneda, contrabando, estafa, etc.). Esta es la 'naturaleza del delito'."
    )
    delitos_df = ind.ind_composicion_delito(conexion)
    mostrar(delitos_df)
    st.plotly_chart(
        grafico_barras(
            delitos_df.to_pandas(), "delito_nombre", "n", "Noticias por delito tipificado"
        ),
        use_container_width=True,
    )

    st.subheader("Territorio (conteo por departamento/municipio)")
    mostrar(ind.ind_territorio_conteo(conexion))

    st.subheader("Serie mensual")
    mostrar(ind.ind_tiempo_mensual(conexion))

    st.subheader("Calidad del lote")
    mostrar(ind.ind_calidad(conexion))


def pagina_fenomenos() -> None:
    st.header("Fenómenos")
    _nota()
    st.caption(
        "Cada fenómeno es una **modalidad** del lavado de activos detectada automáticamente a "
        "partir del texto de los relatos (no el delito tipificado legalmente — para eso ver "
        "Indicadores → Composición por delito). 'n_miembros' es cuántos relatos quedaron "
        "agrupados en esa modalidad; 'Términos dominantes' son las palabras que más distinguen "
        "ese grupo frente a los demás."
    )
    glosario()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()

    if not taxonomia.get("fenomenos"):
        st.info("No hay taxonomía congelada en config/taxonomia/v1.0.yaml.")
        return

    fenomenos_ordenados = sorted(
        taxonomia["fenomenos"], key=lambda f: f.get("n_miembros", 0), reverse=True
    )
    for fenomeno in fenomenos_ordenados:
        titulo = f"{fenomeno['codigo']} — {fenomeno['nombre']} (n={fenomeno['n_miembros']})"
        with st.expander(titulo):
            delito_df = ind.ind_delito_dentro_de_fenomeno(conexion, fenomeno["codigo"])
            sector_df = ind.ind_sector_dentro_de_fenomeno(conexion, fenomeno["codigo"])
            terminos = ", ".join(fenomeno.get("terminos_dominantes", []))
            definicion = fenomeno.get("definicion", "")

            st.write("**Patrones observados en los datos**")
            st.caption(
                "No es una definición jurídica de modus operandi — describe lo que aparece con "
                "más frecuencia en los relatos ya agrupados en este fenómeno."
            )
            patrones = []
            if delito_df.height:
                top_delito = delito_df.row(0, named=True)
                patrones.append(
                    f"delito tipificado más frecuente: **{top_delito['delito_nombre']}** "
                    f"(n={top_delito['n']})"
                )
            sector_df_valido = sector_df.filter(pl.col("sector") != "indeterminado")
            if sector_df_valido.height:
                top_sector = sector_df_valido.row(0, named=True)
                patrones.append(
                    f"sector económico más mencionado: **{top_sector['sector']}** "
                    f"(n={top_sector['n']})"
                )
            if terminos:
                patrones.append(f"términos distintivos del texto (clustering): {terminos}")
            st.markdown("\n".join(f"- {p}" for p in patrones) if patrones else "Sin datos.")

            if definicion and definicion != "pendiente_de_redaccion_por_analista":
                st.write(f"**Definición aprobada por analista:** {definicion}")
            else:
                st.caption(
                    "Definición jurídica de este fenómeno: pendiente de redacción y "
                    "aprobación por un analista."
                )
            st.write(f"**Dominancia de plantilla:** {fenomeno.get('dominancia_plantilla')}")

            st.write("**¿Qué tipo, dentro de este fenómeno?** (delito tipificado y sector)")
            st.caption(
                "El fenómeno es una modalidad amplia; el delito y el sector ya extraídos del "
                "expediente distinguen el tipo específico dentro de ella."
            )
            columna_delito, columna_sector = st.columns(2)
            with columna_delito:
                mostrar(delito_df)
                if delito_df.height:
                    st.plotly_chart(
                        grafico_barras(delito_df.to_pandas(), "delito_nombre", "n"),
                        use_container_width=True,
                        key=f"grafico_delito_{fenomeno['codigo']}",
                    )
            with columna_sector:
                mostrar(sector_df)
                if sector_df.height:
                    st.plotly_chart(
                        grafico_barras(sector_df.to_pandas(), "sector", "n"),
                        use_container_width=True,
                        key=f"grafico_sector_{fenomeno['codigo']}",
                    )

            relatos = conexion.sql(
                "SELECT rp.descripcion_hecho_enmascarada FROM fenomenos.asignacion_fenomeno a "
                "JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid "
                "WHERE a.codigo_fenomeno = ? LIMIT 5",
                params=[fenomeno["codigo"]],
            ).pl()
            st.write("**Relatos representativos (enmascarados):**")
            for i, texto in enumerate(relatos["descripcion_hecho_enmascarada"].to_list()):
                st.text_area(
                    f"relato {i + 1}", texto or "", height=100,
                    key=f"relato_{fenomeno['codigo']}_{i}", label_visibility="collapsed",
                )

    st.subheader("Evolución mensual por fenómeno")
    evolucion = conexion.sql(
        """
        SELECT a.codigo_fenomeno, r.anio_iso_creacion AS anio, r.mes_creacion AS mes,
               count(*) AS n
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE r.fecha_creacion_valida
        GROUP BY a.codigo_fenomeno, r.anio_iso_creacion, r.mes_creacion
        ORDER BY 1, 2, 3
        """
    ).pl()
    mostrar(evolucion, taxonomia=taxonomia)


def pagina_territorio() -> None:
    st.header("Territorio")
    _nota()
    glosario()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()

    st.subheader("Perfil territorial (proporción por fenómeno)")
    st.caption("Por departamento: qué proporción de sus noticias corresponde a cada fenómeno.")
    mostrar(terr.matriz_perfil_territorial(conexion), taxonomia=taxonomia)

    st.subheader("Predominio por departamento")
    st.caption(
        "El fenómeno más frecuente de cada departamento (con al menos 5 noticias) y si supera "
        "estadísticamente al segundo más frecuente (valor p)."
    )
    predominio_df = terr.predominio_territorial(conexion)
    mostrar(predominio_df, taxonomia=taxonomia)
    con_predominio = predominio_df.filter(pl.col("cumple_tamanio_minimo"))
    if con_predominio.height:
        predominio_legible = agregar_nombres_territorio(
            agregar_nombres_fenomeno(con_predominio.to_pandas(), taxonomia)
        )
        st.plotly_chart(
            grafico_barras(predominio_legible, "departamento_hechos", "n_predominante"),
            use_container_width=True,
        )

    st.subheader("Delito predominante por departamento, dentro de un fenómeno")
    st.caption(
        "Cuando el fenómeno predominante es el mismo en casi todos los departamentos (p. ej. "
        "'Lavado de activos', el más amplio y menos diferenciado de la taxonomía — ver "
        "glosario), esto responde una pregunta más útil: dentro de ese fenómeno, ¿qué delito "
        "tipificado predomina en cada departamento?"
    )
    fenomenos_disponibles = taxonomia.get("fenomenos", [])
    if fenomenos_disponibles:
        fenomenos_ordenados = sorted(
            fenomenos_disponibles, key=lambda f: f.get("n_miembros", 0), reverse=True
        )
        codigos_disponibles = [f["codigo"] for f in fenomenos_ordenados]
        nombres_fenomeno_sel = {f["codigo"]: f["nombre"] for f in fenomenos_disponibles}
        fenomeno_delito_sel = st.selectbox(
            "Fenómeno",
            codigos_disponibles,
            format_func=lambda c: nombres_fenomeno_sel.get(c, c),
            key="fenomeno_delito_territorio",
        )
        mostrar(terr.predominio_delito_dentro_de_fenomeno(conexion, fenomeno_delito_sel))

    st.subheader("Sector económico predominante por departamento")
    st.caption(
        "En qué sector económico (hotelero, ganadero, financiero, etc., ya mencionado en el "
        "relato) se concentra más el lavado de activos en cada departamento, con al menos 5 "
        "menciones y la misma prueba frente al segundo sector más mencionado."
    )
    predominio_sector_df = terr.predominio_sector_territorial(conexion)
    mostrar(predominio_sector_df)
    con_predominio_sector = predominio_sector_df.filter(pl.col("cumple_tamanio_minimo"))
    if con_predominio_sector.height:
        predominio_sector_legible = agregar_nombres_territorio(con_predominio_sector.to_pandas())
        st.plotly_chart(
            grafico_barras(predominio_sector_legible, "nombre_territorio", "n_predominante"),
            use_container_width=True,
        )

    st.subheader("Calidad de coordenadas")
    mostrar(terr.resumen_calidad_puntos(conexion))

    st.subheader("Dispersión de puntos válidos por fenómeno")
    mostrar(terr.dispersion_puntos_por_fenomeno(conexion), taxonomia=taxonomia)

    st.subheader("Autocorrelación espacial (Moran I)")
    st.caption(
        "Solo se calcula si hay cobertura suficiente (umbral explícito en "
        "decla.analitica.territorio); si no, devuelve el motivo en vez de un número sin respaldo."
    )
    codigos = _codigos_fenomeno(conexion)
    nombres_fenomeno = {f["codigo"]: f["nombre"] for f in taxonomia.get("fenomenos", [])}
    if codigos:
        fenomeno_sel = st.selectbox(
            "Fenómeno", codigos, format_func=lambda c: nombres_fenomeno.get(c, c)
        )
        nivel_sel = st.radio("Nivel", ["departamento", "municipio"], horizontal=True)
        if st.button("Calcular Moran I"):
            st.write(terr.calcular_moran(conexion, fenomeno_sel, nivel=nivel_sel))

    ruta_mapa_flujos = RAIZ_PROYECTO / "reports" / "agregados" / "i3" / "mapa_flujos.png"
    if ruta_mapa_flujos.exists():
        st.subheader("Flujos hechos → unidad que tramita")
        st.image(str(ruta_mapa_flujos))


def pagina_asociaciones() -> None:
    st.header("Asociaciones")
    _nota()
    st.caption(
        "Asociación estadística, no causalidad. Ver interpretación completa en cada resultado."
    )
    glosario()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()

    if st.button("Fenómeno × delito (chi²/Fisher, V de Cramér)"):
        resultado = aso.chi2_fenomeno_delito(conexion)
        if resultado.get("calculado"):
            tabla = resultado.pop("residuos_estandarizados")
            st.write({etiqueta(k): v for k, v in resultado.items()})
            st.caption(
                "Residuos estandarizados por fenómeno/delito: positivo = más casos de los "
                "esperados si no hubiera relación; negativo = menos de los esperados."
            )
            mostrar(tabla, taxonomia=taxonomia)
        else:
            st.write(resultado)

    if st.button("Reglas de asociación (fenómeno-sector-territorio)"):
        reglas = aso.reglas_asociacion_fenomeno_sector_territorio(conexion)
        reglas_pd = traducir_itemsets_df(reglas.to_pandas(), taxonomia)
        mostrar(reglas_pd)

    if st.button("Poisson/NB con offset (cambios por territorio y periodo)"):
        resultado = aso.poisson_o_nb_offset(conexion)
        if resultado.get("calculado") and "parametros" in resultado:
            parametros = resultado.pop("parametros").to_pandas()
            parametros["termino"] = parametros["termino"].map(
                lambda t: traducir_termino_formula(t, taxonomia)
            )
            st.write({etiqueta(k): v for k, v in resultado.items()})
            mostrar(parametros)
        else:
            st.write(resultado)

    if st.button("Red de co-ocurrencia de menciones (PMI + Louvain)"):
        resultado = aso.red_coocurrencia_menciones(conexion)
        st.write(
            {
                etiqueta(k): v
                for k, v in resultado.items()
                if k not in {"grafo", "comunidad_por_nodo"}
            }
        )

    st.caption(
        "Grafo de conexidad: no construido (entidades.grupo_conexo solo tiene el conteo "
        "declarado NO_CASOS_CONEXOS, no identifica cuáles son los casos conexos — ADR I3)."
    )


def pagina_emergencia() -> None:
    st.header("Emergencia — alertas")
    _nota()
    glosario()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()
    try:
        alertas = conexion.sql("SELECT * FROM oro.alertas ORDER BY p_ajustado_bh").pl()
    except duckdb.CatalogException:
        st.info("Todavía no se ha corrido `make emergencia`.")
        return

    if alertas.height == 0:
        st.info("Sin alertas ni candidatos en el último run de `make emergencia`.")
        return

    mostrar(alertas, taxonomia=taxonomia)
    st.caption(
        "Confirmar o descartar una alerta queda pendiente de una cola de revisión con escritura "
        "(como `app_revision_fenomenos.py` para la taxonomía) — no construida esta ronda (ADR "
        "0015): el foco de este incremento es el resultado analítico, no el flujo de revisión."
    )


def pagina_pronosticos() -> None:
    st.header("Pronósticos — tendencia")
    _nota()
    st.caption(
        "Historia disponible menor a 12 meses (ADR 0016): sin estacionalidad estimable e "
        "intervalos de confianza anchos. El modelo ingenuo (repetir el último valor observado) "
        "es la referencia obligatoria; solo se reporta una tendencia cuando otro método la "
        "supera en el backtest histórico."
    )
    glosario()
    conexion = _conexion()

    st.subheader("Ranking: delito en tendencia")
    st.caption(
        "Por delito tipificado (no por fenómeno — el fenómeno casi siempre es 'lavado de "
        "activos', el único alcance del dataset). Variación % frente al pronóstico ingenuo en "
        "el horizonte más lejano calculado."
    )
    ranking = ind.ranking_tendencia_delito(conexion)
    if ranking.height == 0:
        st.info(
            "Sin tendencia reportable todavía: o no se ha corrido `make prediccion`, o ningún "
            "método con tendencia superó al modelo ingenuo en el backtest."
        )
    else:
        ranking_legible = agregar_nombres_territorio(ranking.to_pandas())
        st.plotly_chart(
            grafico_barras(
                ranking_legible.assign(
                    serie=ranking_legible["delito_nombre"] + " · "
                    + ranking_legible["nombre_territorio"].astype(str)
                ),
                "serie",
                "variacion_pct_vs_ingenuo",
                "Variación % frente al pronóstico ingenuo (top 15)",
            ),
            use_container_width=True,
        )
        mostrar(ranking)

    st.subheader("Serie histórica + pronóstico, por delito y departamento")
    delitos_disponibles = sorted(
        conexion.sql(
            "SELECT DISTINCT delito_nombre FROM plata.registros_limpios "
            "WHERE delito_nombre IS NOT NULL"
        ).pl()["delito_nombre"].to_list()
    )
    if not delitos_disponibles:
        st.info("Sin delitos tipificados disponibles todavía (correr `make etl`).")
        return

    delito_sel = st.selectbox("Delito", delitos_disponibles, key="pronostico_delito_sel")
    series = construir_series_delito_territorio(conexion)
    territorios_delito = sorted(
        series.filter(pl.col("delito_nombre") == delito_sel)["territorio"].unique().to_list()
    )
    if not territorios_delito:
        st.info("Sin serie histórica para este delito.")
        return
    dptos, _ = divipola()
    territorio_sel = st.selectbox(
        "Departamento",
        territorios_delito,
        format_func=lambda c: dptos.get(str(c), c),
        key="pronostico_territorio_sel",
    )

    historico = (
        series.filter(
            (pl.col("delito_nombre") == delito_sel) & (pl.col("territorio") == territorio_sel)
        )
        .sort("indice_periodo")
        .to_pandas()
    )
    historico["periodo_mes"] = historico["indice_periodo"].map(decodificar_indice_periodo)

    try:
        pronosticos = conexion.sql(
            "SELECT * FROM oro.pronosticos_delito WHERE delito_nombre = ? AND territorio = ? "
            "AND metodo = 'ets_tendencia' ORDER BY periodo_pronosticado",
            params=[delito_sel, territorio_sel],
        ).pl().to_pandas()
    except duckdb.CatalogException:
        pronosticos = pd.DataFrame()
    if not pronosticos.empty:
        pronosticos["periodo_mes"] = pronosticos["periodo_pronosticado"].map(
            decodificar_indice_periodo
        )

    nombre_territorio_sel = dptos.get(str(territorio_sel), territorio_sel)
    st.plotly_chart(
        grafico_linea_pronostico(
            historico, pronosticos, f"{delito_sel} — {nombre_territorio_sel}"
        ),
        use_container_width=True,
    )
    if not pronosticos.empty:
        mostrar(pronosticos)


def pagina_buscador() -> None:
    st.header("Buscador semántico de relatos")
    _nota()

    if not RAIZ_EMBEDDINGS.exists():
        st.info("No hay embeddings calculados todavía (correr `make nlp`).")
        return
    lotes = sorted(
        (p for p in RAIZ_EMBEDDINGS.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime
    )
    if not lotes:
        st.info("No hay embeddings calculados todavía (correr `make nlp`).")
        return
    lote_mas_reciente = lotes[-1]

    from decla.comun.configuracion import cargar_yaml
    from decla.texto.buscador_semantico import buscar_similares, vector_de_consulta

    modelo = cargar_yaml(RAIZ_PROYECTO / "config" / "embeddings.yaml")["modelo_defecto"]
    corpus_df = pl.read_parquet(lote_mas_reciente / "relato.parquet").filter(
        pl.col("agregacion") == "media"
    )
    uids_corpus = corpus_df["registro_uid"].to_list()
    vectores_corpus = corpus_df["vector"].to_list()
    corpus = dict(zip(uids_corpus, vectores_corpus, strict=True))

    consulta = st.text_input("Describe el fenómeno que buscas (texto libre)")
    if consulta and st.button("Buscar"):
        vector = vector_de_consulta(consulta, modelo)
        resultados = buscar_similares(vector, corpus, k=10)
        conexion = _conexion()
        for r in resultados:
            texto = conexion.sql(
                "SELECT descripcion_hecho_enmascarada FROM texto.relato_procesado "
                "WHERE registro_uid = ?",
                params=[r.registro_uid],
            ).pl()
            contenido = texto["descripcion_hecho_enmascarada"].to_list()
            st.write(f"**Similitud {r.similitud}**")
            st.text_area(
                "", contenido[0] if contenido else "", height=100,
                key=f"busq_{r.registro_uid}", label_visibility="collapsed",
            )


def pagina_salud_del_sistema() -> None:
    st.header("Salud del sistema")
    _nota()
    glosario()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()

    st.subheader("Último lote procesado")
    ejecuciones = conexion.sql(
        "SELECT * FROM meta.ejecuciones ORDER BY inicio DESC LIMIT 10"
    ).pl() if _tabla_existe(conexion, "meta", "ejecuciones") else None
    if ejecuciones is not None and ejecuciones.height > 0:
        mostrar(ejecuciones)
    else:
        st.info("Sin ejecuciones registradas todavía.")

    st.subheader("Calidad del lote")
    mostrar(ind.ind_calidad(conexion))

    st.subheader("Deriva del último `make lote`")
    if _tabla_existe(conexion, "meta", "historico_cambios"):
        cambios = conexion.sql(
            "SELECT * FROM meta.historico_cambios ORDER BY fecha DESC LIMIT 50"
        ).pl()
        st.write(f"{cambios.height} cambios registrados (últimos 50 mostrados).")
        mostrar(cambios)
    else:
        st.info("Sin `make lote` corrido todavía (solo hay un lote inicial).")

    st.subheader("Evaluación consolidada")
    ruta_evaluacion = RAIZ_PROYECTO / "reports" / "agregados" / "evaluacion" / "v1.md"
    if ruta_evaluacion.exists():
        st.markdown(ruta_evaluacion.read_text(encoding="utf-8"))
    else:
        st.info("Sin `make evaluar` corrido todavía.")

    st.subheader("Alertas abiertas")
    if _tabla_existe(conexion, "oro", "alertas"):
        abiertas = conexion.sql(
            "SELECT * FROM oro.alertas WHERE estado IN ('candidato_en_observacion', 'alerta')"
        ).pl()
        mostrar(abiertas, taxonomia=taxonomia) if abiertas.height else st.info(
            "Sin alertas ni candidatos abiertos."
        )
    else:
        st.info("Sin `make emergencia` corrido todavía.")


def _tabla_existe(conexion: duckdb.DuckDBPyConnection, esquema: str, tabla: str) -> bool:
    resultado = conexion.sql(
        "SELECT count(*) AS n FROM information_schema.tables "
        "WHERE table_schema = ? AND table_name = ?",
        params=[esquema, tabla],
    ).pl()
    return bool(resultado["n"].item())


def main() -> None:
    st.sidebar.title("DECLA")
    opciones = [
        "Indicadores", "Fenómenos", "Territorio", "Asociaciones", "Emergencia", "Pronósticos",
        "Buscador semántico", "Salud del sistema",
    ]
    pagina = st.sidebar.radio("Vista", opciones)
    paginas = {
        "Indicadores": pagina_indicadores,
        "Fenómenos": pagina_fenomenos,
        "Territorio": pagina_territorio,
        "Asociaciones": pagina_asociaciones,
        "Emergencia": pagina_emergencia,
        "Pronósticos": pagina_pronosticos,
        "Salud del sistema": pagina_salud_del_sistema,
        "Buscador semántico": pagina_buscador,
    }
    paginas[pagina]()


main()
