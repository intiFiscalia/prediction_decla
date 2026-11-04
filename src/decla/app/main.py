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
import streamlit as st
import yaml

from decla.analitica import asociaciones as aso
from decla.analitica import indicadores as ind
from decla.analitica import territorio as terr
from decla.comun.duckdb_io import conectar

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
    conexion = _conexion()

    st.subheader("Volumen")
    st.dataframe(ind.ind_volumen(conexion).to_pandas())

    st.subheader("Fenómenos")
    st.dataframe(ind.ind_fenomenos(conexion).to_pandas())

    st.subheader("Sectores económicos mencionados")
    st.dataframe(ind.ind_sectores(conexion).to_pandas())

    st.subheader("Composición por delito")
    st.dataframe(ind.ind_composicion_delito(conexion).to_pandas())

    st.subheader("Territorio (conteo por departamento/municipio)")
    st.dataframe(ind.ind_territorio_conteo(conexion).to_pandas())

    st.subheader("Serie mensual")
    st.dataframe(ind.ind_tiempo_mensual(conexion).to_pandas())

    st.subheader("Calidad del lote")
    st.dataframe(ind.ind_calidad(conexion).to_pandas())


def pagina_fenomenos() -> None:
    st.header("Fenómenos")
    _nota()
    conexion = _conexion()
    taxonomia = _cargar_taxonomia()

    if not taxonomia.get("fenomenos"):
        st.info("No hay taxonomía congelada en config/taxonomia/v1.0.yaml.")
        return

    for fenomeno in taxonomia["fenomenos"]:
        titulo = f"{fenomeno['codigo']} — {fenomeno['nombre']} (n={fenomeno['n_miembros']})"
        with st.expander(titulo):
            st.write(f"**Definición:** {fenomeno['definicion']}")
            terminos = ", ".join(fenomeno.get("terminos_dominantes", []))
            st.write(f"**Términos dominantes:** {terminos}")
            st.write(f"**Dominancia de plantilla:** {fenomeno.get('dominancia_plantilla')}")
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
    st.dataframe(evolucion.to_pandas())


def pagina_territorio() -> None:
    st.header("Territorio")
    _nota()
    conexion = _conexion()

    st.subheader("Perfil territorial (proporción por fenómeno)")
    st.dataframe(terr.matriz_perfil_territorial(conexion).to_pandas())

    st.subheader("Predominio por departamento")
    st.dataframe(terr.predominio_territorial(conexion).to_pandas())

    st.subheader("Calidad de coordenadas")
    st.dataframe(terr.resumen_calidad_puntos(conexion).to_pandas())

    st.subheader("Dispersión de puntos válidos por fenómeno")
    st.dataframe(terr.dispersion_puntos_por_fenomeno(conexion).to_pandas())

    st.subheader("Autocorrelación espacial (Moran I)")
    st.caption(
        "Solo se calcula si hay cobertura suficiente (umbral explícito en "
        "decla.analitica.territorio); si no, devuelve el motivo en vez de un número sin respaldo."
    )
    codigos = _codigos_fenomeno(conexion)
    if codigos:
        fenomeno_sel = st.selectbox("Fenómeno", codigos)
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
    conexion = _conexion()

    if st.button("Fenómeno × delito (chi²/Fisher, V de Cramér)"):
        st.write(aso.chi2_fenomeno_delito(conexion))

    if st.button("Reglas de asociación (fenómeno-sector-territorio)"):
        st.dataframe(aso.reglas_asociacion_fenomeno_sector_territorio(conexion).to_pandas())

    if st.button("Poisson/NB con offset (cambios por territorio y periodo)"):
        resultado = aso.poisson_o_nb_offset(conexion)
        if resultado.get("calculado") and "parametros" in resultado:
            st.write({k: v for k, v in resultado.items() if k != "parametros"})
            st.dataframe(resultado["parametros"].to_pandas())
        else:
            st.write(resultado)

    if st.button("Red de co-ocurrencia de menciones (PMI + Louvain)"):
        resultado = aso.red_coocurrencia_menciones(conexion)
        st.write({k: v for k, v in resultado.items() if k not in {"grafo", "comunidad_por_nodo"}})

    st.caption(
        "Grafo de conexidad: no construido (entidades.grupo_conexo solo tiene el conteo "
        "declarado NO_CASOS_CONEXOS, no identifica cuáles son los casos conexos — ADR I3)."
    )


def pagina_emergencia() -> None:
    st.header("Emergencia — alertas")
    _nota()
    conexion = _conexion()
    try:
        alertas = conexion.sql("SELECT * FROM oro.alertas ORDER BY p_ajustado_bh").pl()
    except duckdb.CatalogException:
        st.info("Todavía no se ha corrido `make emergencia`.")
        return

    if alertas.height == 0:
        st.info("Sin alertas ni candidatos en el último run de `make emergencia`.")
        return

    st.dataframe(alertas.to_pandas())
    st.caption(
        "Confirmar o descartar una alerta queda pendiente de una cola de revisión con escritura "
        "(como `app_revision_fenomenos.py` para la taxonomía) — no construida esta ronda (ADR "
        "0015): el foco de este incremento es el resultado analítico, no el flujo de revisión."
    )


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

    import polars as pl

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


def main() -> None:
    st.sidebar.title("DECLA")
    opciones = [
        "Indicadores", "Fenómenos", "Territorio", "Asociaciones", "Emergencia",
        "Buscador semántico",
    ]
    pagina = st.sidebar.radio("Vista", opciones)
    paginas = {
        "Indicadores": pagina_indicadores,
        "Fenómenos": pagina_fenomenos,
        "Territorio": pagina_territorio,
        "Asociaciones": pagina_asociaciones,
        "Emergencia": pagina_emergencia,
        "Buscador semántico": pagina_buscador,
    }
    paginas[pagina]()


main()
