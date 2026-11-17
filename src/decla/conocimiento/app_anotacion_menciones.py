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

from decla.comun.configuracion import cargar_yaml
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
from decla.conocimiento.sectores import cargar_ciiu

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_CATEGORIAS_MENCIONES = RAIZ_PROYECTO / "config" / "categorias_menciones.yaml"

st.set_page_config(page_title="Anotación de menciones", layout="wide")
st.title("Anotación de menciones (mini-compuerta 2B)")
st.caption(
    "Texto ya enmascarado. Cada calificación se guarda en data/private/ y nunca la lee Claude "
    "Code; solo el resumen agregado sale a reports/agregados/i2/."
)
st.markdown(
    """
    <style>
    div[data-baseweb="popover"] li[role="option"] {
        white-space: nowrap;
        overflow-x: auto;
        text-overflow: initial;
    }
    div[data-baseweb="popover"] li[role="option"] > * {
        white-space: nowrap;
        overflow-x: auto !important;
        text-overflow: initial !important;
        max-width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def _conexion_solo_lectura() -> duckdb.DuckDBPyConnection:
    return conectar(RUTA_DUCKDB, solo_lectura=True)


@st.cache_resource
def _etiquetas_por_categoria() -> dict[str, dict[str, str]]:
    """Texto legible por código, para no mostrar solo el código en 'Valor normalizado'
    (p. ej. un código CIIU numérico como '4661' no dice nada sin su descripción)."""
    etiquetas: dict[str, dict[str, str]] = {}

    config = cargar_yaml(RUTA_CATEGORIAS_MENCIONES)
    for categoria in config.get("categorias", []):
        vocabulario = categoria.get("vocabulario") or []
        mapa = {}
        for entrada in vocabulario:
            texto = entrada.get("definicion") or ", ".join(entrada.get("sinonimos", []))
            if texto:
                mapa[entrada["codigo"]] = texto.strip()
        if mapa:
            etiquetas[categoria["nombre"]] = mapa

    etiquetas["sector"] = {entrada.code: entrada.description for entrada in cargar_ciiu()}
    return etiquetas


def _etiqueta_legible(
    etiquetas: dict[str, dict[str, str]], categoria: str, codigo: str | None
) -> str:
    if not codigo or codigo in ("None", "indeterminado"):
        return ""
    texto = etiquetas.get(categoria, {}).get(codigo)
    return f" — _{texto}_" if texto else " — (sin descripción registrada)"


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
    categorias_disponibles = sorted(menciones["categoria"].unique().to_list())
    categorias_defecto = [c for c in ("sector", "mecanismo") if c in categorias_disponibles]
    categorias_elegidas = st.sidebar.multiselect(
        "Categorías a calificar (el cupo se reparte solo entre estas)",
        categorias_disponibles,
        default=categorias_defecto or categorias_disponibles,
    )
    n_pares_objetivo = st.sidebar.number_input(
        "Menciones a calificar", min_value=20, max_value=500, value=70
    )
    calificador = st.sidebar.text_input("Tu nombre o iniciales", value="")

    menciones = menciones.filter(pl.col("categoria").is_in(categorias_elegidas))

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

        etiquetas = _etiquetas_por_categoria()
        etiqueta = _etiqueta_legible(etiquetas, fila["categoria"], fila["valor_normalizado"])

        st.text_area("Relato (enmascarado)", fila["relato_enmascarado"], height=220)
        st.write(f"**Evidencia:** {fila['texto_evidencia']}")
        st.write(
            f"Valor normalizado: `{fila['valor_normalizado']}`{etiqueta} · "
            f"origen: {fila['origen']} · confianza: {fila['confianza']} · "
            f"polaridad: {fila['polaridad']}"
        )

        notas = st.text_area(
            "Notas / razonamiento (opcional, pero obligatorio cuando el valor correcto no es "
            "una lectura literal del texto, p. ej. una inferencia como 'lingotes de oro "
            "incautados sin origen documentado' → mineria_ilegal_oro)",
            key=f"notas_{mencion_id}",
        )

        col1, col2, col3 = st.columns(3)
        if col1.button("Confirmar"):
            guardar_calificacion_mencion(
                RUTA_CALIFICACIONES_DEFECTO,
                mencion_id,
                fila["categoria"],
                CONFIRMADA,
                calificador,
                notas=notas or None,
            )
            st.session_state["indice"] += 1
            st.rerun()
        if col2.button("Rechazar"):
            guardar_calificacion_mencion(
                RUTA_CALIFICACIONES_DEFECTO,
                mencion_id,
                fila["categoria"],
                RECHAZADA,
                calificador,
                notas=notas or None,
            )
            st.session_state["indice"] += 1
            st.rerun()
        with col3.expander("Corregir"):
            categoria_sel = st.selectbox(
                "Categoría correcta",
                categorias_disponibles,
                index=categorias_disponibles.index(fila["categoria"]),
                help=(
                    "Son los tipos fijos de texto.menciones (mecanismo, sector, bien, lugar, "
                    "...); aquí no se inventan tipos nuevos. Déjalo como está: solo cámbialo "
                    "si el extractor puso la mención en el tipo equivocado (p. ej. etiquetó "
                    "como 'bien' algo que es 'medio_transporte'). Para un CÓDIGO nuevo dentro "
                    "del mismo tipo, usa 'Valor correcto' → '(otro código nuevo)'."
                ),
                key=f"cat_{mencion_id}",
            )
            categoria_corregida = categoria_sel if categoria_sel != fila["categoria"] else None
            categoria_efectiva = categoria_sel

            codigos_categoria = etiquetas.get(categoria_efectiva, {})
            if codigos_categoria:
                opciones_valor = list(codigos_categoria) + ["(otro código nuevo)"]
                valor_sel = st.selectbox(
                    "Valor correcto",
                    opciones_valor,
                    format_func=lambda c: (
                        f"{c} — {codigos_categoria[c]}" if c in codigos_categoria else c
                    ),
                    key=f"valsel_{mencion_id}",
                )
                if valor_sel == "(otro código nuevo)":
                    valor_corregido = st.text_input(
                        "Código nuevo (snake_case)", key=f"valnuevo_{mencion_id}"
                    )
                else:
                    valor_corregido = valor_sel
            else:
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
                    notas=notas or None,
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
