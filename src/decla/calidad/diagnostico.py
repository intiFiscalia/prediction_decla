"""Orquestador de diagnóstico de datos (I0 — Fase 1 completa).

Lee CASOS y RELATOS desde `data/raw/` (o la ruta que se indique), corre todos los módulos de
`decla.calidad`, y publica:
  - `reports/agregados/diagnostico/`: CSVs agregados (con supresión de celdas < 5), `informe.md`
    y 3 gráficos PNG. Es la **única** salida que Claude Code puede leer.
  - `data/private/diagnostico/muestra_lectura/`: muestra de 300 relatos para lectura humana,
    reparada y enmascarada parcialmente. Claude Code nunca abre esta carpeta.

No limpia ni transforma los datos (eso es I1): mide los defectos, no los corrige.

Toda cifra de este informe mide **actividad institucional registrada**, no la incidencia real del
delito; ninguna mención de sector, mecanismo o fenómeno en un relato prueba que el hecho ocurrió
(CLAUDE.md §2.3).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

from decla.calidad import (  # noqa: E402
    cardinalidad,
    categoricas,
    coordenadas,
    fechas,
    relatos,
    temporal,
    territorio,
)
from decla.calidad.muestra import (  # noqa: E402
    N_MUESTRA_DEFECTO,
    construir_muestra,
    escribir_formulario_anotacion,
    escribir_muestra_html,
)
from decla.comun.configuracion import cargar_yaml  # noqa: E402
from decla.comun.duckdb_io import conectar  # noqa: E402
from decla.comun.ejecucion import RegistroEjecucion  # noqa: E402
from decla.comun.supresion import suprimir_celdas_bajas  # noqa: E402
from decla.ingesta.esquema import cargar_contrato, comparar_esquema  # noqa: E402
from decla.ingesta.lectores import TablaLeida, leer_tabla  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_REGLAS_FECHAS = RAIZ_PROYECTO / "config" / "reglas_fechas.yaml"
EXTENSIONES_SOPORTADAS = (".csv", ".xlsx", ".numbers")
COLUMNAS_CATEGORICAS = [
    "ESTADO", "ETAPA", "TIPO_NOTICIA", "TIPO_DILIGENCIA", "COMPETENCIA_DESPACHO",
    "TITULO", "CAPITULO", "ULTIMA_ACTUACION", "Eje temático APLICA", "eje tmeatico APLICA",
    "SECC_DESCRIPCION", "LEY",
]
COLUMNAS_PARA_FALTANTES = ["CASO_FECHA_DENUNCIA", "LAT_DIR_HECHOS", "NUMERO_DOCUMENTO"]
MAX_RELATOS_MINHASH = 5000


def _localizar_archivo(directorio: Path, palabra_clave: str) -> Path | None:
    orden = {".csv": 0, ".xlsx": 1, ".numbers": 2}
    candidatos = [
        p for p in directorio.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES_SOPORTADAS and palabra_clave.lower() in p.name.lower()
    ]
    if not candidatos:
        return None
    return sorted(candidatos, key=lambda p: orden[p.suffix.lower()])[0]


def _cargar_divipola(ruta: Path | None) -> tuple[list[territorio.EntradaDivipola], dict[str, tuple[float, float]], list[str]]:
    advertencias: list[str] = []
    if not ruta or not ruta.exists():
        advertencias.append(
            f"No se encontró DIVIPOLA en {ruta}: normalización territorial y comparación con "
            "centroide se omiten hasta que la persona lo copie a data/referencia/."
        )
        return [], {}, advertencias

    df = pl.read_csv(ruta, infer_schema_length=0)
    entradas = [
        territorio.EntradaDivipola(f["cod_dpto"], f["cod_mpio"], f["departamento"], f["municipio"])
        for f in df.iter_rows(named=True)
    ]
    centroides: dict[str, tuple[float, float]] = {}
    if {"lat_centroide", "long_centroide"}.issubset(df.columns):
        for f in df.iter_rows(named=True):
            if f["lat_centroide"] and f["long_centroide"]:
                centroides[f["cod_mpio"]] = (float(f["lat_centroide"]), float(f["long_centroide"]))
    else:
        advertencias.append("DIVIPOLA sin columnas de centroide: se omite comparación con centroide.")
    return entradas, centroides, advertencias


def _guardar_csv(df: pl.DataFrame, ruta: Path, columnas_conteo: list[str] | None = None) -> None:
    if columnas_conteo:
        df = suprimir_celdas_bajas(df, [c for c in columnas_conteo if c in df.columns])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(ruta)


def _dataclasses_a_df(objetos: list[Any]) -> pl.DataFrame:
    return pl.DataFrame([asdict(o) if not isinstance(o, dict) else o for o in objetos])


def diagnosticar(
    directorio_entrada: Path,
    directorio_salida: Path,
    directorio_privado: Path,
    ruta_divipola: Path | None,
    ruta_duckdb: Path,
    hoy: date | None = None,
    n_muestra: int = N_MUESTRA_DEFECTO,
) -> dict[str, Any]:
    hoy = hoy or date.today()
    directorio_salida.mkdir(parents=True, exist_ok=True)
    directorio_privado.mkdir(parents=True, exist_ok=True)
    advertencias: list[str] = []

    archivo_casos = _localizar_archivo(directorio_entrada, "CASOS")
    archivo_relatos = _localizar_archivo(directorio_entrada, "RELATOS")
    if archivo_casos is None:
        raise FileNotFoundError(f"No se encontró un archivo de CASOS en {directorio_entrada}")
    if archivo_relatos is None:
        raise FileNotFoundError(f"No se encontró un archivo de RELATOS en {directorio_entrada}")

    tabla_casos: TablaLeida = leer_tabla(archivo_casos)
    tabla_relatos: TablaLeida = leer_tabla(archivo_relatos)

    ruta_duckdb.parent.mkdir(parents=True, exist_ok=True)
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    with RegistroEjecucion(
        conexion,
        paso="diagnostico",
        parametros={"archivo_casos": archivo_casos.name, "archivo_relatos": archivo_relatos.name},
    ):
        contrato = cargar_contrato()
        esquema_casos = comparar_esquema(tabla_casos, "CASOS", contrato)
        esquema_relatos = comparar_esquema(tabla_relatos, "RELATOS", contrato)

        resumen_card = cardinalidad.resumir_cardinalidad(tabla_casos)
        resumen_union = cardinalidad.resumir_union(tabla_casos, tabla_relatos)
        hipotesis_grano = cardinalidad.proponer_hipotesis_grano(resumen_card)

        divipola_entradas, centroides, advertencias_divipola = _cargar_divipola(ruta_divipola)
        advertencias.extend(advertencias_divipola)
        cod_mpios_validos = {e.cod_mpio for e in divipola_entradas}
        resumen_caso_noticia = cardinalidad.verificar_hipotesis_caso_noticia(tabla_casos, cod_mpios_validos)

        resultados_territorio = [
            territorio.emparejar_territorio(f.get("DEPARTAMENTO_HECHOS"), f.get("MUNICIPIO_HECHOS"), divipola_entradas)
            for f in tabla_casos.filas
        ] if divipola_entradas else []

        resultados_coordenadas = []
        for i, fila in enumerate(tabla_casos.filas):
            centroide = None
            cod_mpio_resuelto = resultados_territorio[i].cod_mpio if resultados_territorio else None
            if cod_mpio_resuelto:
                centroide = centroides.get(cod_mpio_resuelto)
            resultados_coordenadas.append(
                coordenadas.reparar_coordenadas(fila.get("LAT_DIR_HECHOS"), fila.get("LONG_DIR_HECHOS"), centroide)
            )

        reglas_fechas = cargar_yaml(RUTA_REGLAS_FECHAS)
        valores_invalidos_conocidos = set(reglas_fechas.get("valores_invalidos_conocidos", []))
        resumenes_fecha = {}
        formato_por_columna = {}
        for columna in reglas_fechas.get("columnas_fecha_casos", []):
            valores = [f.get(columna) for f in tabla_casos.filas]
            resumen_col = fechas.evaluar_columna_fecha(columna, valores, hoy, valores_invalidos_conocidos)
            resumenes_fecha[columna] = resumen_col
            formato_por_columna[columna] = resumen_col.formato_detectado

        resumenes_orden = [
            fechas.verificar_orden_logico(tabla_casos.filas, par[0], par[1], formato_por_columna)
            for par in reglas_fechas.get("orden_logico", [])
        ]
        regla_presc = reglas_fechas.get("regla_prescripcion", {})
        resumen_prescripcion = fechas.verificar_prescripcion(
            tabla_casos.filas,
            regla_presc.get("columna_base", "FECHA_HECHO"),
            regla_presc.get("columna_resultado", "CASO_FECHA_PRESCRIPCION"),
            regla_presc.get("anios", 20),
            formato_por_columna,
            regla_presc.get("tolerancia_dias", 0),
        )

        catalogos = {
            col: categoricas.catalogo_frecuencias(col, [f.get(col) for f in tabla_casos.filas])
            for col in COLUMNAS_CATEGORICAS
        }
        delitos_parseados = [categoricas.parsear_delito(f.get("DELITO")) for f in tabla_casos.filas]
        n_delito_parseable = sum(1 for d in delitos_parseados if d.parseable)

        faltantes = {
            col: categoricas.faltantes_por_anio_departamento(tabla_casos.filas, col, "FECHA_CREACION", "DEPARTAMENTO_HECHOS")
            for col in COLUMNAS_PARA_FALTANTES
        }

        textos_relato = [f.get("RELATO") for f in tabla_relatos.filas]
        perfil_long = relatos.perfil_longitud(textos_relato)
        n_mojibake = sum(1 for t in textos_relato if t and relatos.tiene_mojibake(t))
        n_reparados_sin_residuo = 0
        n_reparacion_fallida = 0
        for t in textos_relato:
            if t and relatos.tiene_mojibake(t):
                resultado_rep = relatos.verificar_reparacion_mojibake(t)
                if resultado_rep.fallo_reparacion:
                    n_reparacion_fallida += 1
                elif resultado_rep.sin_residuo:
                    n_reparados_sin_residuo += 1
        n_mayuscula_sostenida = sum(1 for t in textos_relato if t and relatos.es_mayuscula_sostenida(t))
        longitudes_caracteres = [len(t) for t in textos_relato if t]
        longitudes_palabras = [len(t.split()) for t in textos_relato if t]
        resumen_truncamiento = relatos.detectar_posible_truncamiento(longitudes_caracteres)

        conteo_personales: Counter[str] = Counter()
        for t in textos_relato:
            if t:
                conteo_personales.update(relatos.contar_patrones_personales(t))

        pares_relato: list[tuple[str, str, str]] = [
            (f"R{i}", caso_noticia, relato)
            for i, f in enumerate(tabla_relatos.filas)
            if (caso_noticia := f.get("CASO_NOTICIA")) and (relato := f.get("RELATO"))
        ]
        if len(pares_relato) > MAX_RELATOS_MINHASH:
            advertencias.append(
                f"Casi-duplicados: omitido por volumen ({len(pares_relato)} relatos > {MAX_RELATOS_MINHASH})."
            )
            casi_duplicados: list = []
        else:
            casi_duplicados = relatos.detectar_casi_duplicados_entre_noticias(pares_relato)
        noticias_en_casi_duplicados = {p.caso_noticia_a for p in casi_duplicados} | {
            p.caso_noticia_b for p in casi_duplicados
        }

        resumen_temporal = temporal.resumir_temporal(
            [f.get("FECHA_CREACION") for f in tabla_casos.filas],
            formato_por_columna.get("FECHA_CREACION", fechas.FORMATO_AMBIGUO),
        )

        muestra = construir_muestra(tabla_casos.filas, tabla_relatos.filas, n=n_muestra)
        escribir_muestra_html(muestra, directorio_privado / "muestra_lectura" / "muestra.html")
        escribir_formulario_anotacion(muestra, directorio_privado / "muestra_lectura" / "anotacion.csv")

        _publicar_csvs(
            directorio_salida, esquema_casos, esquema_relatos, resumen_card, resumen_union,
            hipotesis_grano, resumen_caso_noticia, resultados_territorio, resultados_coordenadas,
            resumenes_fecha, resumenes_orden, resumen_prescripcion, catalogos, delitos_parseados,
            n_delito_parseable, faltantes, perfil_long, n_mojibake, n_reparados_sin_residuo,
            n_reparacion_fallida, n_mayuscula_sostenida, resumen_truncamiento, conteo_personales,
            len(casi_duplicados), len(noticias_en_casi_duplicados), resumen_temporal,
        )
        _generar_graficos(directorio_salida, resumen_temporal.volumen_mensual, longitudes_palabras, delitos_parseados)
        _escribir_informe(
            directorio_salida, esquema_casos, esquema_relatos, resumen_card, resumen_union,
            hipotesis_grano, resumen_caso_noticia, resultados_territorio, resultados_coordenadas,
            resumenes_fecha, resumenes_orden, resumen_prescripcion, n_delito_parseable,
            len(tabla_casos.filas), perfil_long, n_mojibake, n_reparados_sin_residuo,
            n_reparacion_fallida, n_mayuscula_sostenida, resumen_truncamiento,
            len(casi_duplicados), resumen_temporal, advertencias,
        )

    conexion.close()
    return {
        "n_filas_casos": len(tabla_casos.filas),
        "n_filas_relatos": len(tabla_relatos.filas),
        "advertencias": advertencias,
    }


def _publicar_csvs(
    directorio_salida: Path, esquema_casos, esquema_relatos, resumen_card, resumen_union,
    hipotesis_grano, resumen_caso_noticia, resultados_territorio, resultados_coordenadas,
    resumenes_fecha, resumenes_orden, resumen_prescripcion, catalogos, delitos_parseados,
    n_delito_parseable, faltantes, perfil_long, n_mojibake, n_reparados_sin_residuo,
    n_reparacion_fallida, n_mayuscula_sostenida, resumen_truncamiento, conteo_personales,
    n_casi_duplicados, n_noticias_en_casi_duplicados, resumen_temporal,
) -> None:
    _guardar_csv(_dataclasses_a_df(esquema_casos.resultados), directorio_salida / "esquema_casos.csv")
    _guardar_csv(_dataclasses_a_df(esquema_relatos.resultados), directorio_salida / "esquema_relatos.csv")

    _guardar_csv(pl.DataFrame([{**asdict(resumen_card), "distribucion_filas_por_noticia": json.dumps(resumen_card.distribucion_filas_por_noticia)}]), directorio_salida / "cardinalidad.csv", ["n_filas", "n_caso_id_unicos", "n_caso_noticia_unicos", "n_duplicados_exactos", "n_duplicados_parciales"])
    _guardar_csv(pl.DataFrame([{**asdict(resumen_union), "distribucion_relatos_por_noticia": json.dumps(resumen_union.distribucion_relatos_por_noticia)}]), directorio_salida / "union_casos_relatos.csv", ["n_noticias_casos", "n_noticias_relatos", "n_coincidencias", "n_huerfanos_relatos", "n_casos_sin_relato"])
    _guardar_csv(_dataclasses_a_df(hipotesis_grano), directorio_salida / "hipotesis_grano.csv")
    _guardar_csv(pl.DataFrame([asdict(resumen_caso_noticia)]), directorio_salida / "caso_noticia_hipotesis.csv", ["n_total", "n_longitud_21", "n_prefijo_dane_valido", "n_anio_coincide"])

    if resultados_territorio:
        conteo_metodo = Counter(r.metodo for r in resultados_territorio)
        total = len(resultados_territorio)
        df_territorio = pl.DataFrame([{"metodo": m, "n": n, "pct": round(n / total * 100, 2)} for m, n in conteo_metodo.items()])
        _guardar_csv(df_territorio, directorio_salida / "territorio_resumen.csv", ["n"])

    conteo_coord = Counter(r.metodo for r in resultados_coordenadas)
    total_coord = len(resultados_coordenadas) or 1
    df_coord = pl.DataFrame([{"metodo": m, "n": n, "pct": round(n / total_coord * 100, 2)} for m, n in conteo_coord.items()])
    _guardar_csv(df_coord, directorio_salida / "coordenadas_resumen.csv", ["n"])

    _guardar_csv(pl.DataFrame([asdict(v) for v in resumenes_fecha.values()]), directorio_salida / "fechas_formato.csv", ["n_total", "n_validas", "n_invalidas", "n_futuras"])
    _guardar_csv(_dataclasses_a_df(resumenes_orden), directorio_salida / "fechas_orden_logico.csv", ["n_comparables", "n_violaciones"])
    desviaciones = resumen_prescripcion.desviaciones_dias
    _guardar_csv(
        pl.DataFrame([{
            "n_comparables": resumen_prescripcion.n_comparables,
            "n_cumple_regla": resumen_prescripcion.n_cumple_regla,
            "pct_cumple_regla": resumen_prescripcion.pct_cumple_regla,
            "desviacion_mediana_dias": statistics_median_or_none(desviaciones),
        }]),
        directorio_salida / "fechas_prescripcion.csv",
        ["n_comparables", "n_cumple_regla"],
    )

    for columna, catalogo in catalogos.items():
        filas_catalogo = [{"valor": e.valor, "conteo": e.conteo} for e in catalogo.principales]
        if catalogo.otros_conteo:
            filas_catalogo.append({"valor": f"otros (<5), {catalogo.otros_valores_distintos} valores distintos", "conteo": catalogo.otros_conteo})
        nombre_archivo = "categoricas_" + "".join(c if c.isalnum() else "_" for c in columna).strip("_").lower()
        _guardar_csv(pl.DataFrame(filas_catalogo) if filas_catalogo else pl.DataFrame({"valor": [], "conteo": []}), directorio_salida / f"{nombre_archivo}.csv", ["conteo"])

    _guardar_csv(
        pl.DataFrame([{"n_total": len(delitos_parseados), "n_parseable": n_delito_parseable, "pct_parseable": round(n_delito_parseable / len(delitos_parseados) * 100, 2) if delitos_parseados else 0.0}]),
        directorio_salida / "delito_parseo.csv",
        ["n_total", "n_parseable"],
    )

    for columna, df_faltantes in faltantes.items():
        nombre_archivo = "faltantes_" + "".join(c if c.isalnum() else "_" for c in columna).lower()
        _guardar_csv(df_faltantes, directorio_salida / f"{nombre_archivo}.csv", ["n_filas", "n_faltantes"])

    _guardar_csv(
        pl.DataFrame([{
            "n_relatos": perfil_long.n_relatos,
            "n_vacios": perfil_long.n_vacios,
            **{f"palabras_p{p}": v for p, v in perfil_long.percentiles_palabras.items()},
            **{f"caracteres_p{p}": v for p, v in perfil_long.percentiles_caracteres.items()},
            "n_mojibake": n_mojibake,
            "n_reparados_sin_residuo": n_reparados_sin_residuo,
            "n_reparacion_fallida": n_reparacion_fallida,
            "n_mayuscula_sostenida": n_mayuscula_sostenida,
            "longitud_maxima_caracteres": resumen_truncamiento.longitud_maxima,
            "pct_en_longitud_maxima": resumen_truncamiento.pct_en_maximo,
            "posible_truncamiento": resumen_truncamiento.posible_truncamiento,
            "n_casi_duplicados_entre_noticias": n_casi_duplicados,
            "n_noticias_en_casi_duplicados": n_noticias_en_casi_duplicados,
            **{f"patrones_{k}": v for k, v in conteo_personales.items()},
        }]),
        directorio_salida / "relatos_resumen.csv",
        [
            "n_relatos", "n_mojibake", "n_mayuscula_sostenida",
            "n_casi_duplicados_entre_noticias", "n_noticias_en_casi_duplicados",
        ],
    )

    _guardar_csv(resumen_temporal.volumen_mensual, directorio_salida / "temporal_mensual.csv", ["n_registros"])
    _guardar_csv(
        pl.DataFrame([{
            "n_meses_con_datos": resumen_temporal.n_meses_con_datos,
            "periodo_min": resumen_temporal.periodo_min,
            "periodo_max": resumen_temporal.periodo_max,
            "viable_pronostico": resumen_temporal.viable_pronostico,
            "meses_con_punto_de_cambio": json.dumps(resumen_temporal.meses_con_punto_de_cambio),
        }]),
        directorio_salida / "temporal_resumen.csv",
    )


def statistics_median_or_none(valores: list[int]) -> float | None:
    if not valores:
        return None
    import statistics

    return float(statistics.median(valores))


def _generar_graficos(directorio_salida: Path, volumen_mensual: pl.DataFrame, longitudes_palabras: list[int], delitos_parseados: list) -> None:
    if volumen_mensual.height:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(volumen_mensual["mes"].to_list(), volumen_mensual["n_registros"].to_list())
        ax.set_title("Volumen mensual de registros (actividad institucional registrada)")
        ax.set_xlabel("Mes (FECHA_CREACION)")
        ax.set_ylabel("Registros")
        plt.setp(ax.get_xticklabels(), rotation=90, fontsize=6)
        fig.tight_layout()
        fig.savefig(directorio_salida / "volumen_mensual.png", dpi=120)
        plt.close(fig)

    if longitudes_palabras:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(longitudes_palabras, bins=30)
        ax.set_title("Distribución de longitud de RELATO (palabras)")
        ax.set_xlabel("Palabras")
        ax.set_ylabel("Relatos")
        fig.tight_layout()
        fig.savefig(directorio_salida / "longitud_relato.png", dpi=120)
        plt.close(fig)

    nombres = Counter(d.nombre for d in delitos_parseados if d.nombre)
    if nombres:
        principales = nombres.most_common(10)[::-1]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh([n for n, _ in principales], [c for _, c in principales])
        ax.set_title("Delitos más frecuentes (nombre parseado de DELITO)")
        ax.set_xlabel("Registros")
        fig.tight_layout()
        fig.savefig(directorio_salida / "top_delitos.png", dpi=120)
        plt.close(fig)


def _escribir_informe(
    directorio_salida: Path, esquema_casos, esquema_relatos, resumen_card, resumen_union,
    hipotesis_grano, resumen_caso_noticia, resultados_territorio, resultados_coordenadas,
    resumenes_fecha, resumenes_orden, resumen_prescripcion, n_delito_parseable, n_filas_casos,
    perfil_long, n_mojibake, n_reparados_sin_residuo, n_reparacion_fallida, n_mayuscula_sostenida,
    resumen_truncamiento, n_casi_duplicados, resumen_temporal, advertencias,
) -> None:
    partes = [
        "# Informe de diagnóstico — I0",
        "",
        "**Toda cifra de este informe mide actividad institucional registrada, no la incidencia "
        "real del delito. Una mención en un relato no prueba que el hecho ocurrió ni que una "
        "persona participó.** (CLAUDE.md §2.3)",
        "",
        f"Generado para {n_filas_casos} filas de CASOS.",
        "",
        "## Advertencias generales",
    ]
    partes += [f"- {a}" for a in advertencias] if advertencias else ["- (ninguna)"]

    partes += [
        "",
        "## Esquema",
        f"- CASOS: {len(esquema_casos.columnas_esperadas_faltantes)} columnas esperadas faltantes, "
        f"{len(esquema_casos.columnas_nuevas)} columnas nuevas no contempladas en el contrato.",
        f"- RELATOS: {len(esquema_relatos.columnas_esperadas_faltantes)} columnas esperadas "
        f"faltantes, {len(esquema_relatos.columnas_nuevas)} columnas nuevas.",
        "",
        "## Cardinalidad y grano (ver hipotesis_grano.csv, cardinalidad.csv)",
    ]
    for h in hipotesis_grano:
        partes.append(f"- **{h.nombre}** (puntaje {h.puntaje:.2f}): {h.evidencia}")

    partes += [
        "",
        "## Unión CASOS↔RELATOS",
        f"- Noticias en CASOS: {resumen_union.n_noticias_casos}; en RELATOS: {resumen_union.n_noticias_relatos}.",
        f"- Coincidencias: {resumen_union.n_coincidencias} "
        f"({resumen_union.pct_cobertura_casos}% de CASOS, {resumen_union.pct_cobertura_relatos}% de RELATOS).",
        f"- Huérfanos en RELATOS (sin CASOS): {resumen_union.n_huerfanos_relatos}. "
        f"Casos sin relato: {resumen_union.n_casos_sin_relato}.",
        "",
        "## Hipótesis de estructura de CASO_NOTICIA (21 dígitos)",
        f"- {resumen_caso_noticia.pct_longitud_21}% de los valores tiene 21 dígitos.",
        f"- De esos, {resumen_caso_noticia.pct_prefijo_dane_valido}% tiene un prefijo que existe en DIVIPOLA "
        f"y {resumen_caso_noticia.pct_anio_coincide}% tiene el año embebido igual al de FECHA_CREACION.",
        "",
        "## Territorio",
    ]
    if resultados_territorio:
        conteo_metodo = Counter(r.metodo for r in resultados_territorio)
        total = len(resultados_territorio)
        for metodo, n in conteo_metodo.most_common():
            partes.append(f"- {metodo}: {n} ({round(n / total * 100, 2)}%)")
    else:
        partes.append("- No se pudo normalizar: falta DIVIPOLA real en data/referencia/.")

    conteo_coord = Counter(r.metodo for r in resultados_coordenadas)
    total_coord = len(resultados_coordenadas) or 1
    partes += ["", "## Coordenadas"]
    for metodo, n in conteo_coord.most_common():
        partes.append(f"- {metodo}: {n} ({round(n / total_coord * 100, 2)}%)")

    partes += ["", "## Fechas"]
    for columna, resumen in resumenes_fecha.items():
        partes.append(
            f"- {columna}: formato detectado {resumen.formato_detectado} "
            f"(confianza {resumen.confianza_formato}), {resumen.pct_validas}% válidas, "
            f"{resumen.n_futuras} futuras, {resumen.n_valores_invalidos_conocidos} valores sentinel conocidos."
        )
    partes.append("")
    partes.append("### Orden lógico esperado")
    for r in resumenes_orden:
        partes.append(
            f"- {r.columna_anterior} ≤ {r.columna_posterior}: {r.pct_violaciones}% de violaciones "
            f"sobre {r.n_comparables} filas comparables."
        )
    partes.append("")
    partes.append(
        f"### Regla de prescripción (hecho + 20 años): {resumen_prescripcion.pct_cumple_regla}% "
        f"cumple exactamente sobre {resumen_prescripcion.n_comparables} filas comparables."
    )

    partes += [
        "",
        "## DELITO",
        f"- {n_delito_parseable} de {n_filas_casos} valores se separaron en nombre/artículo/cuantía "
        "con el patrón esperado (ver delito_parseo.csv y categoricas_delito* si aplica).",
        "",
        "## RELATO",
        f"- {perfil_long.n_relatos} relatos ({perfil_long.n_vacios} vacíos); mediana de longitud "
        f"{perfil_long.percentiles_palabras.get(50, 0):.0f} palabras.",
        f"- {n_mojibake} relatos con mojibake cirílico detectado; "
        f"{n_reparados_sin_residuo} se repararon sin residuo, {n_reparacion_fallida} no se pudieron reparar.",
        f"- {n_mayuscula_sostenida} relatos en mayúsculas sostenidas.",
        f"- Posible truncamiento: {resumen_truncamiento.posible_truncamiento} "
        f"({resumen_truncamiento.pct_en_maximo}% de los relatos en la longitud máxima observada).",
        f"- {n_casi_duplicados} pares de relatos casi-idénticos entre noticias distintas (MinHash).",
        "",
        "## Estabilidad temporal y viabilidad de pronósticos",
        f"- {resumen_temporal.nota_viabilidad}",
        f"- Periodo observado: {resumen_temporal.periodo_min} a {resumen_temporal.periodo_max}.",
        f"- Meses con posible punto de cambio: {resumen_temporal.meses_con_punto_de_cambio or '(ninguno)'}.",
        "",
        "## Muestra de lectura humana",
        "- Ver `data/private/diagnostico/muestra_lectura/` (no se publica aquí: puede contener "
        "nombres propios sin enmascarar).",
    ]

    (directorio_salida / "informe.md").write_text("\n".join(partes), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RAIZ_PROYECTO / "data" / "raw")
    parser.add_argument("--salida", type=Path, default=RAIZ_PROYECTO / "reports" / "agregados" / "diagnostico")
    parser.add_argument("--privado", type=Path, default=RAIZ_PROYECTO / "data" / "private" / "diagnostico")
    parser.add_argument("--divipola", type=Path, default=RAIZ_PROYECTO / "data" / "referencia" / "divipola.csv")
    parser.add_argument("--duckdb", type=Path, default=RAIZ_PROYECTO / "data" / "warehouse.duckdb")
    parser.add_argument("--n-muestra", type=int, default=N_MUESTRA_DEFECTO)
    args = parser.parse_args(argv)

    resultado = diagnosticar(args.entrada, args.salida, args.privado, args.divipola, args.duckdb, n_muestra=args.n_muestra)
    print(f"Diagnóstico completo: {resultado['n_filas_casos']} filas de CASOS, {resultado['n_filas_relatos']} de RELATOS.")
    for advertencia in resultado["advertencias"]:
        print(f"  advertencia: {advertencia}")
    print(f"Informe en {args.salida / 'informe.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
