"""Interfaz Streamlit de `herramienta_anotacion_fenomeno.py` (ADR 0024; plan_trabajo.md §7.3).

Uso: `uv run streamlit run src/decla/fenomenos/app_anotacion_fenomeno.py` (o `make
anotar-fenomenos`).

Muestra el RELATO COMPLETO ya enmascarado (nunca el original) junto con los códigos que el
borrador de clustering le asignó, para que un analista confirme o corrija el conjunto de
fenómenos (multietiqueta). Distinta de `decla.conocimiento.app_anotacion_menciones` (esa califica
menciones puntuales, no el relato entero).
"""

from __future__ import annotations

import html
from pathlib import Path

import duckdb
import polars as pl
import streamlit as st

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import conectar
from decla.fenomenos.clasificador_llm import ClienteMLX, clasificar_relato
from decla.fenomenos.herramienta_anotacion_fenomeno import (
    CONFIRMADA,
    CORREGIDA,
    RUTA_CALIFICACIONES_DEFECTO,
    RUTA_CANDIDATOS_DEFECTO,
    RUTA_RESUMEN_DEFECTO,
    CandidatoRelato,
    agrupar_calificaciones_por_calificador,
    calcular_cobertura_por_codigo,
    calcular_kappa_por_codigo,
    cargar_calificaciones_fenomeno,
    cargar_codigos_fenomeno,
    descripcion_codigo,
    escribir_candidatos_fenomeno_nuevo,
    escribir_resumen,
    guardar_calificacion_fenomeno,
    identificar_candidatos_fenomeno_nuevo,
    muestrear_relatos_estratificado,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_UMBRALES = RAIZ_PROYECTO / "config" / "umbrales.yaml"
RUTA_MODELO_LLM = RAIZ_PROYECTO / "models" / "qwen2.5-14b-instruct-4bit"

st.set_page_config(page_title="Anotación de fenómenos", layout="wide")
st.title("Anotación de fenómenos por relato (ADR 0024)")
st.caption(
    "Texto ya enmascarado. Cada calificación se guarda en data/private/ y nunca la lee Claude "
    "Code; solo el resumen agregado sale a reports/agregados/i4/."
)


def _tooltip_codigos_sugeridos(codigos_sugeridos: list[str]) -> str:
    """Ícono '?' con tooltip nativo del navegador (atributo `title`, se ve al hacer hover):
    explica qué implica cada código que sugirió el borrador, para no dejar al analista
    adivinando qué significa p. ej. `incautacion_y_conteo_de_efectivo`."""
    if not codigos_sugeridos:
        texto = descripcion_codigo("no_clasificado")
    else:
        texto = " | ".join(f"{c}: {descripcion_codigo(c)}" for c in codigos_sugeridos)
    return (
        f'<span title="{html.escape(texto)}" '
        'style="cursor: help; border: 1px solid #888; border-radius: 50%; padding: 0 6px; '
        'font-size: 0.85em; color: #888;">?</span>'
    )


@st.cache_resource
def _conexion_solo_lectura() -> duckdb.DuckDBPyConnection:
    return conectar(RUTA_DUCKDB, solo_lectura=True)


@st.cache_resource
def _cliente_llm() -> ClienteMLX:
    """Carga el modelo una sola vez por sesión (ADR 0026) — tarda, por eso se cachea y solo se
    invoca si el analista activa la casilla de sugerencia LLM."""
    return ClienteMLX(RUTA_MODELO_LLM)


@st.cache_data
def _cargar_relatos_con_borrador() -> pl.DataFrame:
    """Relatos enmascarados con sus códigos sugeridos por el borrador de clustering (puede ser
    ninguno: ese relato queda como candidato implícito a `no_clasificado`)."""
    conexion = _conexion_solo_lectura()
    asignaciones = conexion.sql(
        "SELECT registro_uid, codigo_fenomeno FROM fenomenos.asignacion_fenomeno"
    ).pl()
    relatos = conexion.sql(
        "SELECT registro_uid, relato_enmascarado FROM texto.relato_procesado"
    ).pl()
    por_registro = (
        asignaciones.group_by("registro_uid")
        .agg(pl.col("codigo_fenomeno").alias("codigos_sugeridos"))
    )
    return relatos.join(por_registro, on="registro_uid", how="left")


def main() -> None:
    codigos_disponibles = cargar_codigos_fenomeno()
    relatos = _cargar_relatos_con_borrador()

    n_objetivo = st.sidebar.number_input(
        "Relatos a calificar", min_value=10, max_value=300, value=50
    )
    calificador = st.sidebar.text_input("Tu nombre o iniciales", value="")
    usar_llm = st.sidebar.checkbox(
        "Sugerir con LLM local (ADR 0026)",
        value=False,
        help=(
            "Reemplaza la sugerencia del borrador de clustering por la del modelo Qwen2.5-14B "
            "local, con más detalle y evidencia. Más lento: ~5-15s por relato."
        ),
    )

    if "cola_fenomenos" not in st.session_state:
        candidatos = [
            CandidatoRelato(
                registro_uid=fila["registro_uid"],
                codigos_sugeridos=tuple(sorted(fila["codigos_sugeridos"] or [])),
            )
            for fila in relatos.iter_rows(named=True)
        ]
        st.session_state["cola_fenomenos"] = muestrear_relatos_estratificado(
            candidatos, int(n_objetivo)
        )
        st.session_state["indice_fenomenos"] = 0

    cola = st.session_state["cola_fenomenos"]
    indice = st.session_state["indice_fenomenos"]
    relatos_por_id = {fila["registro_uid"]: fila for fila in relatos.iter_rows(named=True)}

    if indice >= len(cola):
        st.success(f"Terminaste los {len(cola)} relatos. Calcula el resumen abajo.")
    else:
        registro_uid = cola[indice]
        fila = relatos_por_id[registro_uid]
        codigos_sugeridos = sorted(fila["codigos_sugeridos"] or [])
        resultado_llm = None
        fuente_sugerencia = "el borrador de clustering"

        if usar_llm:
            try:
                resultado_llm = clasificar_relato(
                    _cliente_llm(), fila["relato_enmascarado"], codigos_disponibles
                )
                codigos_sugeridos = sorted(resultado_llm.codigos)
                fuente_sugerencia = "el LLM local (Qwen2.5-14B, ADR 0026)"
            except Exception as error:  # noqa: BLE001 — cualquier falla del LLM no debe tumbar la anotación
                st.warning(
                    f"El LLM no pudo sugerir para este relato ({error}); se usa el borrador de "
                    "clustering."
                )

        st.progress(indice / len(cola) if cola else 0.0)
        st.text_area("Relato (enmascarado)", fila["relato_enmascarado"], height=220)
        texto_codigos = ", ".join(codigos_sugeridos) if codigos_sugeridos else "(ninguno)"
        if resultado_llm is not None:
            st.caption(
                f"Evidencia citada por el LLM: {resultado_llm.evidencia or '(sin evidencia)'} "
                f"— confianza: {resultado_llm.confianza}"
            )
        st.markdown(
            f"**Códigos sugeridos por {fuente_sugerencia}:** {texto_codigos} "
            f"{_tooltip_codigos_sugeridos(codigos_sugeridos)}",
            unsafe_allow_html=True,
        )
        notas = st.text_area("Notas (opcional)", key=f"notas_{registro_uid}")

        col1, col2 = st.columns(2)
        if col1.button("Confirmar"):
            guardar_calificacion_fenomeno(
                RUTA_CALIFICACIONES_DEFECTO,
                registro_uid,
                codigos_sugeridos,
                CONFIRMADA,
                calificador,
                notas=notas or None,
            )
            st.session_state["indice_fenomenos"] += 1
            st.rerun()
        with col2.expander("Corregir"):
            st.caption("Marca TODOS los códigos correctos (ninguno marcado = no_clasificado).")
            codigos_corregidos = [
                codigo
                for codigo in codigos_disponibles
                if st.checkbox(
                    codigo,
                    value=codigo in codigos_sugeridos,
                    help=descripcion_codigo(codigo),
                    key=f"chk_{registro_uid}_{codigo}",
                )
            ]
            otro_termino = st.text_input(
                "Otro (especifica el fenómeno que ves, si ninguno de los anteriores aplica)",
                key=f"otro_{registro_uid}",
                help=(
                    "No se agrega solo a la taxonomía: queda contado como candidato en "
                    "reports/agregados/i4/candidatos_fenomeno_nuevo.csv para que se revise en "
                    "un taller (mismo criterio que mecanismos nuevos, ADR 0020)."
                ),
            )
            if otro_termino.strip():
                codigos_corregidos = [*codigos_corregidos, otro_termino.strip()]
            if st.button("Guardar corrección", key=f"btn_{registro_uid}"):
                guardar_calificacion_fenomeno(
                    RUTA_CALIFICACIONES_DEFECTO,
                    registro_uid,
                    codigos_sugeridos,
                    CORREGIDA,
                    calificador,
                    codigos_corregidos=codigos_corregidos,
                    notas=notas or None,
                )
                st.session_state["indice_fenomenos"] += 1
                st.rerun()

    st.divider()
    if st.button("Calcular resumen agregado"):
        minimo_por_codigo = cargar_yaml(RUTA_UMBRALES)["clasificador_fenomeno"][
            "minimo_ejemplos_por_codigo"
        ]
        calificaciones = cargar_calificaciones_fenomeno(RUTA_CALIFICACIONES_DEFECTO)
        cobertura = calcular_cobertura_por_codigo(calificaciones, codigos_disponibles)

        por_calificador = agrupar_calificaciones_por_calificador(calificaciones)
        kappa_por_codigo = None
        n_doble_anotados = None
        if len(por_calificador) >= 2:
            dos_mayores = sorted(
                por_calificador, key=lambda nombre: -len(por_calificador[nombre])
            )[:2]
            grupo_a, grupo_b = por_calificador[dos_mayores[0]], por_calificador[dos_mayores[1]]
            kappa_por_codigo = calcular_kappa_por_codigo(grupo_a, grupo_b, codigos_disponibles)
            uids_a = {fila["registro_uid"] for fila in grupo_a}
            uids_b = {fila["registro_uid"] for fila in grupo_b}
            n_doble_anotados = len(uids_a & uids_b)
            if len(por_calificador) > 2:
                st.caption(
                    f"Hay {len(por_calificador)} calificadores distintos; el kappa se calculó "
                    f"entre los dos con más calificaciones ({dos_mayores[0]!r}, "
                    f"{dos_mayores[1]!r})."
                )
        else:
            st.caption(
                "Aún no hay doble anotación: todas las calificaciones vienen de un solo "
                "calificador. El kappa de Cohen no se puede calcular todavía."
            )

        n_relatos_totales = len({fila["registro_uid"] for fila in calificaciones})
        escribir_resumen(
            cobertura,
            minimo_por_codigo=minimo_por_codigo,
            kappa_por_codigo=kappa_por_codigo,
            n_relatos_doble_anotados=n_doble_anotados,
            n_relatos_totales=n_relatos_totales,
            ruta_salida=RUTA_RESUMEN_DEFECTO,
        )
        candidatos_nuevos = identificar_candidatos_fenomeno_nuevo(
            calificaciones, set(codigos_disponibles)
        )
        escribir_candidatos_fenomeno_nuevo(candidatos_nuevos, ruta_salida=RUTA_CANDIDATOS_DEFECTO)
        st.write(cobertura)
        if kappa_por_codigo:
            st.write("Kappa de Cohen por código:", kappa_por_codigo)
        st.success(f"Resumen escrito en {RUTA_RESUMEN_DEFECTO}")
        if candidatos_nuevos:
            st.write("Candidatos a fenómeno nuevo (pendientes de taller de revisión):")
            st.write(candidatos_nuevos)


main()
