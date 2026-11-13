"""Capa de presentación de la app Streamlit (Fase 11): traduce nombres de columna técnicos,
códigos DIVIPOLA y códigos de fenómeno a texto legible para una persona sin formación técnica.

No cambia ningún cálculo ni nombre de columna en `decla.analitica`/`decla.emergencia`: todo el
renombrado ocurre solo en la tabla que se muestra en pantalla (CLAUDE.md, "ninguna capa modifica
la anterior" aplica también aquí — esta capa es puramente de presentación).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DIVIPOLA = RAIZ_PROYECTO / "data" / "referencia" / "divipola.csv"

NO_CLASIFICADO = "(no_clasificado)"

ETIQUETAS: dict[str, str] = {
    "n": "Cantidad de noticias",
    "n_registros": "Cantidad de registros",
    "n_noticias": "Cantidad de noticias",
    "n_casos": "Cantidad de casos",
    "n_total": "Total de noticias en el territorio",
    "n_total_mpio": "Total de noticias en el municipio",
    "n_nacional": "Total nacional del delito",
    "n_total_nacional": "Total nacional de noticias",
    "pct": "% del total",
    "pct_participacion": "% de relatos con este fenómeno",
    "pct_predominante": "% del fenómeno predominante",
    "pct_con_conexos_declarados": "% con casos conexos declarados",
    "razon_registros_noticia": "Registros por noticia",
    "codigo_fenomeno": "Fenómeno (modalidad del lavado)",
    "fenomeno_predominante": "Fenómeno predominante",
    "fenomeno_segundo": "Segundo fenómeno más frecuente",
    "delito_nombre": "Delito tipificado",
    "delito_predominante": "Delito predominante",
    "delito_segundo": "Segundo delito más frecuente",
    "sector": "Sector económico mencionado",
    "sector_predominante": "Sector predominante",
    "sector_segundo": "Segundo sector más frecuente",
    "mecanismo": "Mecanismo (modus operandi detectado)",
    "articulo_cp": "Artículo del Código Penal",
    "estado_norm": "Estado del caso",
    "etapa_norm": "Etapa procesal",
    "cod_dpto_hechos": "Código departamento",
    "cod_mpio_hechos": "Código municipio",
    "departamento_hechos": "Departamento",
    "municipio_hechos": "Municipio",
    "cod_dpto": "Código departamento",
    "cod_mpio": "Código municipio",
    "departamento": "Departamento",
    "municipio": "Municipio",
    "territorio": "Código de territorio",
    "nombre_territorio": "Territorio",
    "anio": "Año",
    "mes": "Mes",
    "periodo": "Periodo (año-mes)",
    "n_registros_anio_anterior": "Cantidad el mismo mes del año anterior",
    "variacion_interanual_pct": "Variación % frente al año anterior",
    "poblacion_total": "Población del municipio (DANE)",
    "tasa_por_100k": "Tasa por 100.000 habitantes",
    "tasa_suavizada_por_100k": "Tasa suavizada por 100.000 habitantes",
    "cociente_localizacion": "Cociente de localización",
    "p": "Valor p",
    "p_ajustado_bh": "Valor p ajustado (Benjamini-Hochberg)",
    "estadistico": "Estadístico de la prueba",
    "metodo": "Método",
    "tamanio_efecto_v_cramer": "Tamaño de efecto (V de Cramér)",
    "calidad_coord_hechos": "Calidad de la coordenada",
    "centroide_lat": "Latitud del centroide",
    "centroide_long": "Longitud del centroide",
    "dispersion_grados": "Dispersión (grados)",
    "n_puntos_validos": "Puntos con coordenada exacta",
    "p_valor_supera_segundo": "Valor p (¿supera al segundo?)",
    "cumple_tamanio_minimo": "¿Tiene casos suficientes?",
    "n_predominante": "Cantidad del fenómeno predominante",
    "n_segundo": "Cantidad del segundo fenómeno",
    "mediana_dias_hecho_denuncia": "Mediana de días entre el hecho y la denuncia",
    "mediana_dias_denuncia_creacion": "Mediana de días entre la denuncia y la creación del caso",
    "mediana_dias_creacion_asignacion": "Mediana de días entre la creación y la asignación",
    "n_cerca_prescripcion_declarada": "Casos cerca de prescribir (<365 días)",
    "n_con_conexos_declarados": "Con casos conexos declarados",
    "categoria_sector": "Origen del dato de sector",
    "run_id": "Identificador de la ejecución",
    "paso": "Paso del proceso",
    "inicio": "Inicio",
    "fin": "Fin",
    "commit_git": "Versión del código (commit)",
    "parametros": "Parámetros usados",
    "estado": "Estado",
    "caso_notica": "Noticia criminal",
    "campo": "Campo modificado",
    "valor_anterior": "Valor anterior",
    "valor_nuevo": "Valor nuevo",
    "lote_id_nuevo": "Lote en el que cambió",
    "fecha": "Fecha",
    "antecedents": "Si se observa",
    "consequents": "Entonces también aparece",
    "support": "Soporte (% de casos con este patrón)",
    "confidence": "Confianza (% de veces que se cumple)",
    "lift": "Lift (fuerza de la asociación; 1 = independiente)",
}

AYUDAS: dict[str, str] = {
    "n": "Número de noticias criminales en esta categoría. Mide actividad institucional "
    "registrada, no cuántos delitos ocurrieron en la realidad.",
    "pct": "Porcentaje sobre el total de esta tabla.",
    "pct_participacion": "Porcentaje de relatos que incluyen este fenómeno. Un mismo relato "
    "puede tener más de un fenómeno asignado, así que la suma de esta columna puede superar "
    "100%.",
    "codigo_fenomeno": "Modalidad del lavado de activos detectada automáticamente a partir del "
    "texto del relato (agrupamiento semántico), no el delito tipificado legalmente. Para el "
    "delito formal ver 'Composición por delito'.",
    "delito_nombre": "Delito tal como quedó tipificado en el campo DELITO del expediente (texto "
    "original separado en nombre, artículo y cuantía).",
    "articulo_cp": "Número del artículo del Código Penal colombiano citado en el expediente "
    "para este delito.",
    "cod_dpto_hechos": "Código DIVIPOLA del departamento donde ocurrieron los hechos. Ver la "
    "columna 'Departamento' para el nombre.",
    "cod_mpio_hechos": "Código DIVIPOLA del municipio donde ocurrieron los hechos. Ver la "
    "columna 'Municipio' para el nombre.",
    "cod_dpto": "Código DIVIPOLA del departamento. Ver la columna 'Departamento' para el nombre.",
    "cod_mpio": "Código DIVIPOLA del municipio. Ver la columna 'Municipio' para el nombre.",
    "territorio": "Código DIVIPOLA de departamento. Ver la columna de nombre añadida junto a "
    "esta.",
    "p": "Probabilidad de que esta diferencia se deba al azar. Menor a 0.05 suele considerarse "
    "estadísticamente significativo.",
    "p_ajustado_bh": "Valor p corregido por comparaciones múltiples (Benjamini-Hochberg), para "
    "no sobreestimar cuántos resultados son significativos al probar muchas combinaciones.",
    "razon_registros_noticia": "Cuántos registros de CASOS corresponden a cada noticia "
    "criminal; 1 significa que no hay duplicados por noticia.",
    "cociente_localizacion": "Mayor a 1: ese delito está más concentrado en ese municipio que "
    "en el promedio nacional. Menor a 1: menos concentrado.",
    "p_valor_supera_segundo": "Probabilidad de que la diferencia entre el fenómeno más "
    "frecuente y el segundo se deba al azar. Menor a 0.05 indica que el predominio es "
    "estadísticamente sólido.",
    "tasa_por_100k": "Registros divididos por la población del municipio, por cada 100.000 "
    "habitantes. Queda vacío si no hay población de referencia para ese municipio/año.",
    "variacion_interanual_pct": "Cambio porcentual frente al mismo mes del año anterior.",
    "calidad_coord_hechos": "Qué tan confiable es la coordenada geográfica del hecho ('exacta', "
    "'reparada', etc.).",
    "n_cerca_prescripcion_declarada": "Casos cuya fecha de prescripción declarada en el "
    "expediente vence en menos de un año.",
    "mecanismo": "Modus operandi detectado por similitud de texto contra 12 definiciones "
    "semilla (compra de ganado, minería ilegal de oro, empresas fachada, testaferros, "
    "criptoactivos, etc.). 'no_clasificado' significa que ningún mecanismo superó el umbral de "
    "confianza — es un resultado legítimo, no un error.",
    "categoria_sector": "'explicito' = el relato lo dice directamente; "
    "'inferido_alta_confianza' = lo dedujo el modelo con alta certeza; 'indeterminado' = no se "
    "pudo establecer con ninguno de los dos.",
    "antecedents": "Combinación de fenómeno, sector y/o territorio que se observa junta en el "
    "relato.",
    "consequents": "Lo que tiende a acompañar a la combinación anterior.",
    "support": "En qué fracción de todos los relatos aparece esta combinación completa.",
    "confidence": "De los relatos donde aparece 'Si se observa', en qué fracción también "
    "aparece 'Entonces también aparece'.",
    "lift": "Mayor a 1: la asociación es más fuerte que si fueran independientes. 1: "
    "independientes. Menor a 1: aparecen juntos menos de lo esperado.",
}


def etiqueta(columna: str) -> str:
    """Nombre legible de una columna; si no está catalogada, la convierte de snake_case a texto
    plano en vez de dejar el nombre técnico tal cual.
    """
    if columna in ETIQUETAS:
        return ETIQUETAS[columna]
    return columna.replace("_", " ").strip().capitalize()


@st.cache_data
def divipola() -> tuple[dict[str, str], dict[str, str]]:
    if not RUTA_DIVIPOLA.exists():
        return {}, {}
    df = pl.read_csv(RUTA_DIVIPOLA, infer_schema_length=0)
    dptos = dict(zip(df["cod_dpto"].to_list(), df["departamento"].to_list(), strict=True))
    mpios = dict(zip(df["cod_mpio"].to_list(), df["municipio"].to_list(), strict=True))
    return dptos, mpios


_COLUMNAS_DPTO = {"cod_dpto_hechos", "cod_dpto"}
_COLUMNAS_MPIO = {"cod_mpio_hechos", "cod_mpio"}


def agregar_nombres_territorio(df: pd.DataFrame) -> pd.DataFrame:
    """Reemplaza cualquier código de departamento o municipio por su nombre DIVIPOLA (el código
    por sí solo no aporta nada a un usuario sin formación técnica). Para la columna genérica
    `territorio` (usada en emergencia/asociaciones, siempre a nivel de departamento) resuelve
    igual, sin asumir que es municipio.
    """
    dptos, mpios = divipola()
    if not dptos and not mpios:
        return df
    df = df.copy()
    for col in df.columns:
        if col in _COLUMNAS_DPTO:
            df[col] = df[col].map(dptos).fillna("(no resuelto)")
        elif col in _COLUMNAS_MPIO:
            df[col] = df[col].map(mpios).fillna("(no resuelto)")
        elif col == "territorio":
            df[col] = df[col].map(
                lambda v: dptos.get(str(v)) or mpios.get(str(v)) or "(no resuelto)"
            )
    return df.rename(
        columns={
            "cod_dpto_hechos": "departamento_hechos",
            "cod_mpio_hechos": "municipio_hechos",
            "cod_dpto": "departamento",
            "cod_mpio": "municipio",
            "territorio": "nombre_territorio",
        }
    )


def decodificar_indice_periodo(valor: Any) -> str:
    """`oro.alertas.periodo` guarda `indice_periodo = año*12 + mes` (entero creciente para la
    regresión de tendencia, `decla.emergencia.linea_base`), nunca pensado para mostrarse. Lo
    decodifica a 'AAAA-MM'.
    """
    if valor is None:
        return "(sin dato)"
    entero = int(valor)
    anio, mes = divmod(entero, 12)
    if mes == 0:
        mes = 12
        anio -= 1
    return f"{anio:04d}-{mes:02d}"


def formatear_periodo_alertas(df: pd.DataFrame) -> pd.DataFrame:
    """Decodifica la columna `periodo` cuando viene como `indice_periodo` entero (salida cruda
    de `oro.alertas`), sin tocar columnas `periodo` que ya vengan formateadas como texto
    'AAAA-MM' (p. ej. las de `decla.analitica.asociaciones`).
    """
    if "periodo" not in df.columns or not pd.api.types.is_integer_dtype(df["periodo"]):
        return df
    df = df.copy()
    df["periodo"] = df["periodo"].map(decodificar_indice_periodo)
    return df


def agregar_nombres_fenomeno(df: pd.DataFrame, taxonomia: dict) -> pd.DataFrame:
    """Reemplaza cualquier código de fenómeno por su nombre legible (de
    `config/taxonomia/v1.0.yaml`) y renombra las columnas dinámicas de las tablas pivote (una
    columna por fenómeno) a su nombre.
    """
    nombres = {f["codigo"]: f["nombre"] for f in taxonomia.get("fenomenos", [])}
    nombres[NO_CLASIFICADO] = "Sin fenómeno asignado"
    if not nombres:
        return df
    df = df.copy()
    for col in ("codigo_fenomeno", "fenomeno_predominante", "fenomeno_segundo"):
        if col in df.columns:
            df[col] = df[col].map(nombres).fillna(df[col])
    renombres = {c: nombres[c] for c in df.columns if c in nombres}
    if renombres:
        df = df.rename(columns=renombres)
    return df


# Nombres legibles de los 13 códigos semilla de `config/categorias_menciones.yaml` (categoría
# "mecanismo"). Es una lista cerrada y conocida (no datos abiertos): prettificar sus códigos no
# es inventar información, solo traducir snake_case a una frase legible.
# "lavado_activos_sin_detalle" (ADR 0021) es distinto de "no_clasificado": el primero es un
# hallazgo positivo (el relato confirma lavado de activos, sin técnica identificable); el
# segundo es que el clasificador no alcanzó la confianza mínima para decidir nada.
MECANISMOS: dict[str, str] = {
    "fraccionamiento_consignaciones": "Fraccionamiento de consignaciones",
    "empresas_fachada": "Empresas fachada",
    "testaferros": "Testaferros",
    "contrabando_mercancias": "Contrabando de mercancías",
    "contrabando_combustibles": "Contrabando de combustibles",
    "subfacturacion": "Subfacturación",
    "compra_ganado": "Compra de ganado",
    "compra_inmuebles": "Compra de inmuebles",
    "mineria_ilegal_oro": "Minería ilegal de oro",
    "giros_casas_cambio": "Giros y casas de cambio",
    "criptoactivos": "Criptoactivos",
    "captacion_ilegal": "Captación ilegal de dinero",
    "lavado_activos_sin_detalle": "Lavado de activos sin detalle de mecanismo",
    "no_clasificado": "Sin mecanismo identificado (confianza insuficiente)",
}


def agregar_nombres_mecanismo(df: pd.DataFrame) -> pd.DataFrame:
    """Reemplaza el código de mecanismo (`compra_ganado`, `mineria_ilegal_oro`, etc.) por su
    nombre legible. Deja cualquier código nuevo que se añada al diccionario semilla sin traducir
    (snake_case) en vez de ocultarlo.
    """
    if "mecanismo" not in df.columns:
        return df
    df = df.copy()
    df["mecanismo"] = df["mecanismo"].map(lambda v: MECANISMOS.get(v, v))
    return df


_PATRON_ITEM = re.compile(r"(fenomeno|sector|territorio)=([\w\-]+)")


def traducir_itemset(texto: str, taxonomia: dict) -> str:
    """Traduce cadenas tipo `fenomeno=lavado_de_activos, territorio=05` (salida cruda de
    `reglas_asociacion_fenomeno_sector_territorio`) a algo legible, resolviendo el código de
    fenómeno y el código DIVIPOLA incluidos en el texto.
    """
    nombres = {f["codigo"]: f["nombre"] for f in taxonomia.get("fenomenos", [])}
    dptos, mpios = divipola()

    def _sub(m: re.Match[str]) -> str:
        clave, valor = m.group(1), m.group(2)
        if clave == "fenomeno":
            return f"fenómeno: {nombres.get(valor, valor)}"
        if clave == "territorio":
            return f"territorio: {dptos.get(valor) or mpios.get(valor) or valor}"
        return f"sector: {valor}"

    return _PATRON_ITEM.sub(_sub, texto)


def traducir_itemsets_df(df: pd.DataFrame, taxonomia: dict) -> pd.DataFrame:
    df = df.copy()
    for col in ("antecedents", "consequents"):
        if col in df.columns:
            df[col] = df[col].map(lambda v: traducir_itemset(str(v), taxonomia))
    return df


_PATRON_TERMINO_FORMULA = re.compile(r"C\((\w+)\)\[T\.([\w\-]+)\]")


def traducir_termino_formula(texto: str, taxonomia: dict) -> str:
    """Traduce términos de fórmula de statsmodels (`C(codigo_fenomeno)[T.lavado_de_activos]`,
    salida cruda de `poisson_o_nb_offset`) a texto legible, resolviendo fenómeno/territorio.
    """
    nombres = {f["codigo"]: f["nombre"] for f in taxonomia.get("fenomenos", [])}
    dptos, mpios = divipola()

    def _sub(m: re.Match[str]) -> str:
        variable, valor = m.group(1), m.group(2)
        if variable == "codigo_fenomeno":
            return f"fenómeno: {nombres.get(valor, valor)}"
        if variable == "territorio":
            return f"territorio: {dptos.get(valor) or mpios.get(valor) or valor}"
        if variable == "periodo":
            return f"periodo: {valor}"
        return f"{variable}: {valor}"

    traducido = _PATRON_TERMINO_FORMULA.sub(_sub, texto)
    return "Intercepto (línea base)" if traducido == "Intercept" else traducido


def config_columnas(df: pd.DataFrame) -> dict[str, Any]:
    return {
        col: st.column_config.Column(label=etiqueta(col), help=AYUDAS.get(col))
        for col in df.columns
    }


def mostrar(datos: pl.DataFrame | pd.DataFrame, taxonomia: dict | None = None, **kwargs) -> None:
    """Reemplazo de `st.dataframe` que añade nombres DIVIPOLA, nombres de fenómeno y
    etiquetas/ayudas legibles para cada columna, sin tocar los datos subyacentes.
    """
    df = datos.to_pandas() if isinstance(datos, pl.DataFrame) else datos
    if df.empty and len(df.columns) == 0:
        st.caption("Sin datos para mostrar.")
        return
    df = formatear_periodo_alertas(df)
    df = agregar_nombres_territorio(df)
    df = agregar_nombres_mecanismo(df)
    if taxonomia is not None:
        df = agregar_nombres_fenomeno(df, taxonomia)
    st.dataframe(df, column_config=config_columnas(df), **kwargs)


def grafico_barras(
    df: pd.DataFrame,
    columna_categoria: str,
    columna_valor: str,
    titulo: str = "",
    maximo_barras: int = 15,
) -> go.Figure:
    """Barras horizontales ordenadas de mayor a menor valor (nunca en el orden de llegada de la
    tabla) — la lectura de "qué es lo más relevante" no debería depender de ordenar una tabla a
    mano. Se recorta a `maximo_barras` para no saturar el gráfico en categorías con muchos valores
    distintos (p. ej. 1122 municipios).
    """
    datos = df[[columna_categoria, columna_valor]].dropna()
    datos = datos.sort_values(columna_valor, ascending=False).head(maximo_barras)
    datos = datos.sort_values(columna_valor, ascending=True)  # ascendente: la más alta queda arriba
    fig = px.bar(
        datos,
        x=columna_valor,
        y=columna_categoria,
        orientation="h",
        title=titulo,
        labels={
            columna_valor: etiqueta(columna_valor),
            columna_categoria: etiqueta(columna_categoria),
        },
    )
    fig.update_layout(margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig


def grafico_linea_pronostico(
    historico: pd.DataFrame, pronostico: pd.DataFrame, titulo: str = ""
) -> go.Figure:
    """Serie histórica (`periodo_mes`, `n`) + pronóstico (`periodo_mes`, `valor_punto`,
    `intervalo_80_inf/sup`) de un solo método, con la banda de intervalo 80% sombreada. Nunca
    oculta que el intervalo es ancho — ADR 0016 (historia corta, sin estacionalidad estimable).
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=historico["periodo_mes"], y=historico["n"], mode="lines+markers",
            name="Observado", line={"color": "#1f77b4"},
        )
    )
    if not pronostico.empty:
        fig.add_trace(
            go.Scatter(
                x=pronostico["periodo_mes"], y=pronostico["valor_punto"], mode="lines+markers",
                name=f"Pronóstico ({pronostico['metodo'].iloc[0]})",
                line={"color": "#d62728", "dash": "dash"},
            )
        )
        if pronostico["intervalo_80_inf"].notna().all():
            fig.add_trace(
                go.Scatter(
                    x=list(pronostico["periodo_mes"]) + list(pronostico["periodo_mes"])[::-1],
                    y=list(pronostico["intervalo_80_sup"])
                    + list(pronostico["intervalo_80_inf"])[::-1],
                    fill="toself", fillcolor="rgba(214,39,40,0.15)",
                    line={"color": "rgba(255,255,255,0)"}, name="Intervalo 80%",
                    hoverinfo="skip",
                )
            )
    fig.update_layout(title=titulo, margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig


def glosario() -> None:
    with st.expander("ℹ️ Glosario — qué significan los términos de esta app"):
        st.markdown(
            "- **Noticia criminal / caso**: una investigación registrada en el sistema (SPOA).\n"
            "- **n**: cantidad de noticias en esa categoría. Mide actividad institucional "
            "*registrada*, no cuántos delitos ocurrieron realmente.\n"
            "- **%**: porcentaje sobre el total de la tabla donde aparece.\n"
            "- **Fenómeno**: la modalidad del lavado de activos detectada automáticamente a "
            "partir del texto del relato (por ejemplo, a través de empresas, con efectivo, en "
            "organización criminal). No es el delito tipificado legalmente — todos los casos de "
            "este sistema son, por alcance, de lavado de activos; el fenómeno dice *cómo* se "
            "hizo.\n"
            "- **Delito / artículo del Código Penal**: la tipificación legal formal que "
            "registró la fiscalía en el expediente (puede ser lavado de activos u otro delito "
            "conexo, como enriquecimiento ilícito, contrabando o falsificación de moneda).\n"
            "- **Departamento / municipio**: nombre oficial según DIVIPOLA (DANE), resuelto a "
            "partir del código interno que usa el sistema.\n"
            "- **Valor p**: probabilidad de que un resultado se deba al azar. Menor a 0.05 "
            "suele considerarse estadísticamente significativo.\n"
            "- **Cociente de localización**: mayor a 1 = ese delito está más concentrado en ese "
            "municipio que en el promedio nacional.\n"
            "- **Explícito / inferido / indeterminado**: de dónde salió un dato — 'explícito' lo "
            "dice el relato directamente, 'inferido' lo dedujo un modelo, 'indeterminado' no se "
            "pudo establecer con ninguno de los dos."
        )
