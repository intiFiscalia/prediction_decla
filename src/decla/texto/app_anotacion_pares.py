"""Interfaz Streamlit de `herramienta_anotacion_pares.py` (plan_trabajo.md §6.1 paso 8(b)).

Uso: `uv run streamlit run src/decla/texto/app_anotacion_pares.py`.

Muestra pares de relatos YA ENMASCARADOS (nunca el texto original) para que un analista califique
"mismo fenómeno" / "distinto" / "no estoy seguro". Las calificaciones se guardan en
`data/private/anotacion_pares/calificaciones.csv` (bloqueado para Claude Code); el resumen
agregado (Spearman, precisión aproximada) se exporta a `reports/agregados/i2/`.

No es la página final de la app multipágina de I3 (plan_trabajo.md Fase 11): es una herramienta
de anotación independiente para la mini-compuerta 2A.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import streamlit as st

from decla.comun.duckdb_io import conectar
from decla.texto.herramienta_anotacion_pares import (
    DISTINTO,
    MISMO_FENOMENO,
    NO_SEGURO,
    RUTA_CALIFICACIONES_DEFECTO,
    RUTA_RESUMEN_DEFECTO,
    calcular_acuerdo,
    cargar_calificaciones,
    escribir_resumen,
    guardar_calificacion,
    muestrear_pares,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_EMBEDDINGS = RAIZ_PROYECTO / "data" / "embeddings"

st.set_page_config(page_title="Anotación de pares de relatos", layout="wide")
st.title("Anotación de pares de relatos (mini-compuerta 2A)")
st.caption(
    "Texto ya enmascarado. Cada calificación se guarda en data/private/ y nunca la lee Claude "
    "Code; solo el resumen agregado sale a reports/agregados/i2/."
)


@st.cache_resource
def _conexion_solo_lectura() -> duckdb.DuckDBPyConnection:
    return conectar(RUTA_DUCKDB, solo_lectura=True)


@st.cache_data
def _cargar_relatos() -> pl.DataFrame:
    conexion = _conexion_solo_lectura()
    return conexion.sql(
        "SELECT registro_uid, relato_enmascarado FROM texto.relato_procesado "
        "WHERE relato_enmascarado IS NOT NULL AND relato_enmascarado != ''"
    ).pl()


@st.cache_data
def _cargar_vectores(lote_id: str) -> dict[str, list[float]]:
    ruta = RUTA_EMBEDDINGS / lote_id / "relato.parquet"
    if not ruta.exists():
        return {}
    df = pl.read_parquet(ruta).filter(pl.col("agregacion") == "media")
    return dict(zip(df["registro_uid"].to_list(), df["vector"].to_list(), strict=True))


def main() -> None:
    relatos = _cargar_relatos()
    uids = relatos["registro_uid"].to_list()
    textos = relatos["relato_enmascarado"].to_list()
    texto_por_uid = dict(zip(uids, textos, strict=True))

    n_pares_objetivo = st.sidebar.number_input(
        "Pares a calificar", min_value=50, max_value=500, value=200
    )
    calificador = st.sidebar.text_input("Tu nombre o iniciales", value="")

    if "pares" not in st.session_state:
        st.session_state["pares"] = muestrear_pares(list(texto_por_uid), int(n_pares_objetivo))
        st.session_state["indice"] = 0

    pares = st.session_state["pares"]
    indice = st.session_state["indice"]

    if indice >= len(pares):
        st.success(f"Terminaste los {len(pares)} pares. Calcula el resumen abajo.")
    else:
        uid_a, uid_b = pares[indice]
        st.progress(indice / len(pares))
        st.write(f"Par {indice + 1} de {len(pares)}")

        columna_a, columna_b = st.columns(2)
        columna_a.text_area("Relato A", texto_por_uid[uid_a], height=300)
        columna_b.text_area("Relato B", texto_por_uid[uid_b], height=300)

        col1, col2, col3 = st.columns(3)
        if col1.button("Mismo fenómeno"):
            guardar_calificacion(
                RUTA_CALIFICACIONES_DEFECTO, uid_a, uid_b, MISMO_FENOMENO, calificador
            )
            st.session_state["indice"] += 1
            st.rerun()
        if col2.button("Distinto"):
            guardar_calificacion(RUTA_CALIFICACIONES_DEFECTO, uid_a, uid_b, DISTINTO, calificador)
            st.session_state["indice"] += 1
            st.rerun()
        if col3.button("No estoy seguro"):
            guardar_calificacion(RUTA_CALIFICACIONES_DEFECTO, uid_a, uid_b, NO_SEGURO, calificador)
            st.session_state["indice"] += 1
            st.rerun()

    st.divider()
    if st.button("Calcular resumen agregado"):
        calificaciones = cargar_calificaciones(RUTA_CALIFICACIONES_DEFECTO)
        lote_id = st.text_input("lote_id de los embeddings a usar", value="")
        vectores = _cargar_vectores(lote_id) if lote_id else {}
        resumen = calcular_acuerdo(calificaciones, vectores)
        escribir_resumen(resumen, RUTA_RESUMEN_DEFECTO)
        st.write(resumen)
        st.success(f"Resumen escrito en {RUTA_RESUMEN_DEFECTO}")


main()
