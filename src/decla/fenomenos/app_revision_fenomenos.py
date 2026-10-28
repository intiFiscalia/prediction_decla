"""Interfaz Streamlit del taller de revisión de grupos (plan_trabajo.md §7.2; Fase 6, Bloque 2C).

Uso: `uv run streamlit run src/decla/fenomenos/app_revision_fenomenos.py`.

Abre `data/warehouse.duckdb` en lectura-escritura para guardar decisiones en
`revision.decisiones_taxonomia`: **no correr al mismo tiempo que** `make etl/nlp/conocimiento/
fenomenos` (DuckDB admite un solo escritor, `decla.comun.duckdb_io`).

Muestra la ficha de cada grupo (términos, menciones dominantes, medoides/bordes YA
ENMASCARADOS) para aprobar, renombrar, fusionar, dividir, marcar como artefacto o descartar; y la
prueba de intrusión (5 relatos de un grupo + 1 intruso, mezclados).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import streamlit as st

from decla.comun.duckdb_io import conectar
from decla.fenomenos.herramienta_revision import (
    APROBAR,
    ARTEFACTO,
    DESCARTAR,
    DIVIDIR,
    FUSIONAR,
    RENOMBRAR,
    calcular_tasa_intrusion,
    cargar_decisiones,
    cargar_resultados_intrusion,
    generar_caso_intrusion,
    guardar_decision,
    registrar_resultado_intrusion,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Revisión de grupos (taller de taxonomía)", layout="wide")
st.title("Taller de revisión de grupos descubiertos (mini-compuerta 2C)")
st.caption(
    "Texto ya enmascarado. Las decisiones se guardan en revision.decisiones_taxonomia "
    "(DuckDB). No corras esta app al mismo tiempo que make etl/nlp/conocimiento/fenomenos."
)


@st.cache_resource
def _conexion() -> duckdb.DuckDBPyConnection:
    return conectar(RUTA_DUCKDB, solo_lectura=False)


@st.cache_data
def _cargar_grupos() -> pl.DataFrame:
    return _conexion().sql("SELECT * FROM fenomenos.grupos_descubiertos").pl()


@st.cache_data
def _cargar_asignacion() -> pl.DataFrame:
    return _conexion().sql(
        "SELECT a.registro_uid, a.grupo_id, r.relato_enmascarado "
        "FROM fenomenos.grupo_asignacion_borrador a "
        "JOIN texto.relato_procesado r ON a.registro_uid = r.registro_uid"
    ).pl()


def _pagina_fichas(grupos: pl.DataFrame, calificador: str) -> None:
    st.header("Fichas de grupo")
    for fila in grupos.iter_rows(named=True):
        with st.expander(f"Grupo {fila['grupo_id']} (n={fila['n_miembros']})"):
            st.write(f"**Términos dominantes:** {fila['terminos_c_tfidf']}")
            st.write(
                f"Dominancia de plantilla: {fila['dominancia_plantilla']} · "
                f"Dominancia de unidad: {fila['dominancia_unidad']}"
            )
            if fila["dominancia_plantilla"] > 0.7:
                st.warning(
                    "Dominancia de plantilla alta: revisar si este grupo refleja un fenómeno "
                    "real o solo el estilo de redacción (ADR 0010)."
                )

            col1, col2, col3, col4, col5 = st.columns(5)
            if col1.button("Aprobar", key=f"apr_{fila['grupo_id']}"):
                guardar_decision(_conexion(), fila["grupo_id"], APROBAR, calificador)
                st.success("Guardado")
            if col2.button("Artefacto", key=f"art_{fila['grupo_id']}"):
                guardar_decision(_conexion(), fila["grupo_id"], ARTEFACTO, calificador)
                st.success("Guardado")
            if col3.button("Descartar", key=f"des_{fila['grupo_id']}"):
                guardar_decision(_conexion(), fila["grupo_id"], DESCARTAR, calificador)
                st.success("Guardado")
            if col4.button("Dividir", key=f"div_{fila['grupo_id']}"):
                guardar_decision(_conexion(), fila["grupo_id"], DIVIDIR, calificador)
                st.success("Guardado")

            nombre_nuevo = col5.text_input("Renombrar a", key=f"nombre_{fila['grupo_id']}")
            if col5.button("Guardar nombre", key=f"guardar_nombre_{fila['grupo_id']}"):
                guardar_decision(
                    _conexion(), fila["grupo_id"], RENOMBRAR, calificador, nombre_nuevo=nombre_nuevo
                )
                st.success("Guardado")

            grupo_destino = st.selectbox(
                "Fusionar con el grupo",
                [g for g in grupos["grupo_id"].to_list() if g != fila["grupo_id"]],
                key=f"fusion_{fila['grupo_id']}",
            )
            if st.button("Guardar fusión", key=f"guardar_fusion_{fila['grupo_id']}"):
                guardar_decision(
                    _conexion(),
                    fila["grupo_id"],
                    FUSIONAR,
                    calificador,
                    grupo_fusion_destino=grupo_destino,
                )
                st.success("Guardado")


def _pagina_intrusion(asignacion: pl.DataFrame, calificador: str) -> None:
    st.header("Prueba de intrusión")
    grupos_disponibles = asignacion["grupo_id"].unique().to_list()
    grupo_elegido = st.selectbox("Grupo a probar", grupos_disponibles)

    registros_del_grupo = asignacion.filter(pl.col("grupo_id") == grupo_elegido)[
        "registro_uid"
    ].to_list()
    registros_de_otro_grupo = asignacion.filter(pl.col("grupo_id") != grupo_elegido)[
        "registro_uid"
    ].to_list()

    semilla = st.number_input("Semilla del caso", min_value=0, value=1)
    caso = generar_caso_intrusion(
        grupo_elegido, registros_del_grupo, registros_de_otro_grupo, int(semilla)
    )
    if caso is None:
        st.info("Este grupo no tiene suficientes relatos para la prueba de intrusión.")
        return

    uids = asignacion["registro_uid"].to_list()
    textos = asignacion["relato_enmascarado"].to_list()
    texto_por_uid = dict(zip(uids, textos, strict=True))
    for i, uid in enumerate(caso.registros_uid_mostrados):
        st.text_area(f"Relato {i + 1}", texto_por_uid.get(uid, ""), height=150, key=f"intr_{uid}")

    respuesta = st.number_input(
        "¿Cuál relato es el intruso? (1-6)", min_value=1, max_value=6, value=1
    )
    if st.button("Calificar"):
        acierto = (respuesta - 1) == caso.indice_intruso
        registrar_resultado_intrusion(_conexion(), grupo_elegido, acierto, calificador)
        st.success("¡Correcto!" if acierto else "No era ese — se registró el intento.")


def main() -> None:
    calificador = st.sidebar.text_input("Tu nombre o iniciales", value="")
    grupos = _cargar_grupos()
    asignacion = _cargar_asignacion()

    pagina = st.sidebar.radio("Vista", ["Fichas de grupo", "Prueba de intrusión", "Resumen"])
    if pagina == "Fichas de grupo":
        _pagina_fichas(grupos, calificador)
    elif pagina == "Prueba de intrusión":
        _pagina_intrusion(asignacion, calificador)
    else:
        st.header("Resumen")
        decisiones = cargar_decisiones(_conexion())
        resultados_intrusion = cargar_resultados_intrusion(_conexion())
        st.write(f"Decisiones registradas: {len(decisiones)}")
        st.write(f"Tasa de acierto en intrusión: {calcular_tasa_intrusion(resultados_intrusion)}")
        st.write(decisiones)


main()
