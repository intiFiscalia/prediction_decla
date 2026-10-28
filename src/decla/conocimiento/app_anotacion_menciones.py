"""Interfaz Streamlit de `herramienta_anotacion_menciones.py` (plan_trabajo.md §6.1 paso 5,
Fase 5; mini-compuerta 2B).

Uso: `uv run streamlit run src/decla/conocimiento/app_anotacion_menciones.py`.

Muestra menciones candidatas sobre texto YA ENMASCARADO (nunca el original) para que un analista
confirme, rechace o corrija cada una. Las calificaciones se guardan en
`data/private/anotacion_menciones/calificaciones.csv` (bloqueado para Claude Code); el resumen
agregado (precisión aproximada por categoría) se exporta a `reports/agregados/i2/`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import streamlit as st

from decla.comun.duckdb_io import conectar
from decla.conocimiento.herramienta_anotacion_menciones import (
    CONFIRMADA,
    CORREGIDA,
    RECHAZADA,
    RUTA_CALIFICACIONES_DEFECTO,
    RUTA_RESUMEN_DEFECTO,
    CandidatoMencion,
    calcular_metricas_por_categoria,
    cargar_calificaciones_menciones,
    escribir_resumen,
    guardar_calificacion_mencion,
    muestrear_menciones_estratificado_activo,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Anotación de menciones", layout="wide")
st.title("Anotación de menciones (mini-compuerta 2B)")
st.caption(
    "Texto ya enmascarado. Cada calificación se guarda en data/private/ y nunca la lee Claude "
    "Code; solo el resumen agregado sale a reports/agregados/i2/."
)


@st.cache_resource
def _conexion_solo_lectura() -> duckdb.DuckDBPyConnection:
    return conectar(RUTA_DUCKDB, solo_lectura=True)


@st.cache_data
def _cargar_menciones() -> pl.DataFrame:
    conexion = _conexion_solo_lectura()
    return conexion.sql(
        "SELECT m.mencion_id, m.registro_uid, m.categoria, m.subcategoria, "
        "       m.valor_normalizado, m.texto_evidencia, m.segmento, m.origen, "
        "       m.polaridad, m.confianza, r.relato_enmascarado "
        "FROM texto.menciones m "
        "JOIN texto.relato_procesado r ON m.registro_uid = r.registro_uid"
    ).pl()


def main() -> None:
    menciones = _cargar_menciones()
    n_pares_objetivo = st.sidebar.number_input(
        "Menciones a calificar", min_value=20, max_value=500, value=70
    )
    calificador = st.sidebar.text_input("Tu nombre o iniciales", value="")

    if "cola" not in st.session_state:
        candidatos = [
            CandidatoMencion(fila["mencion_id"], fila["categoria"], fila["confianza"])
            for fila in menciones.iter_rows(named=True)
        ]
        st.session_state["cola"] = muestrear_menciones_estratificado_activo(
            candidatos, int(n_pares_objetivo)
        )
        st.session_state["indice"] = 0

    cola = st.session_state["cola"]
    indice = st.session_state["indice"]
    menciones_por_id = {fila["mencion_id"]: fila for fila in menciones.iter_rows(named=True)}

    if indice >= len(cola):
        st.success(f"Terminaste las {len(cola)} menciones. Calcula el resumen abajo.")
    else:
        mencion_id = cola[indice]
        fila = menciones_por_id[mencion_id]
        st.progress(indice / len(cola))
        st.write(f"Mención {indice + 1} de {len(cola)} — categoría: **{fila['categoria']}**")

        st.text_area("Relato (enmascarado)", fila["relato_enmascarado"], height=220)
        st.write(f"**Evidencia:** {fila['texto_evidencia']}")
        st.write(
            f"Valor normalizado: `{fila['valor_normalizado']}` · "
            f"origen: {fila['origen']} · confianza: {fila['confianza']} · "
            f"polaridad: {fila['polaridad']}"
        )

        col1, col2, col3 = st.columns(3)
        if col1.button("Confirmar"):
            guardar_calificacion_mencion(
                RUTA_CALIFICACIONES_DEFECTO, mencion_id, fila["categoria"], CONFIRMADA, calificador
            )
            st.session_state["indice"] += 1
            st.rerun()
        if col2.button("Rechazar"):
            guardar_calificacion_mencion(
                RUTA_CALIFICACIONES_DEFECTO, mencion_id, fila["categoria"], RECHAZADA, calificador
            )
            st.session_state["indice"] += 1
            st.rerun()
        with col3.expander("Corregir"):
            categoria_corregida = st.text_input("Categoría correcta", key=f"cat_{mencion_id}")
            valor_corregido = st.text_input("Valor correcto", key=f"val_{mencion_id}")
            if st.button("Guardar corrección", key=f"btn_{mencion_id}"):
                guardar_calificacion_mencion(
                    RUTA_CALIFICACIONES_DEFECTO,
                    mencion_id,
                    fila["categoria"],
                    CORREGIDA,
                    calificador,
                    categoria_corregida=categoria_corregida or None,
                    valor_corregido=valor_corregido or None,
                )
                st.session_state["indice"] += 1
                st.rerun()

    st.divider()
    if st.button("Calcular resumen agregado"):
        calificaciones = cargar_calificaciones_menciones(RUTA_CALIFICACIONES_DEFECTO)
        metricas = calcular_metricas_por_categoria(calificaciones)
        escribir_resumen(metricas, RUTA_RESUMEN_DEFECTO)
        st.write(metricas)
        st.success(f"Resumen escrito en {RUTA_RESUMEN_DEFECTO}")


main()
