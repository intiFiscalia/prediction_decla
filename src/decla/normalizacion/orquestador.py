"""Orquestador de la capa plata (plan_trabajo.md Fase 3; CLAUDE.md §2.4).

Aplica, en orden, validación → alcance → identificadores → fechas → territorio → coordenadas →
delito → categóricas → derivados → seudonimización, y escribe `plata.registros_limpios`,
`plata.dim_territorio`, `plata.dim_tiempo`, `plata.dim_despacho`, `plata.dim_delito` y
`plata.reporte_calidad`. No repara `RELATO` (eso vive en `entidades.relato`, I1 tarea 4): este
módulo solo procesa `CASOS`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from decla.calidad.esquemas import conciliar, escribir_cuarentena, validar_tabla
from decla.calidad.territorio import EntradaDivipola
from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import escribir_tabla_polars
from decla.ingesta.esquema import cargar_contrato
from decla.normalizacion.alcance import filtrar_por_alcance
from decla.normalizacion.categoricas import normalizar_fila_categoricas
from decla.normalizacion.coordenadas import cargar_geometrias_municipios, clasificar_coordenada
from decla.normalizacion.delito import construir_dim_delito, normalizar_delito
from decla.normalizacion.derivados import (
    derivar_componentes_fecha,
    dias_a_prescripcion_declarada,
    dias_entre,
    mismo_dpto_unidad_hechos,
    mismo_mpio,
)
from decla.normalizacion.fechas import normalizar_columna_fecha
from decla.normalizacion.identificadores import descomponer_caso_noticia, limpiar_identificador
from decla.normalizacion.seudonimizacion import obtener_o_crear_clave, seudonimizar
from decla.normalizacion.territorio import cargar_excepciones_manuales, emparejar_con_manual

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_REGLAS_FECHAS = RAIZ_PROYECTO / "config" / "reglas_fechas.yaml"
RUTA_ALCANCE = RAIZ_PROYECTO / "config" / "alcance_tematico.yaml"
RUTA_TERRITORIO_MANUAL = RAIZ_PROYECTO / "config" / "territorio_manual.yaml"
RUTA_DIVIPOLA = RAIZ_PROYECTO / "data" / "referencia" / "divipola.csv"
RUTA_POBLACION = RAIZ_PROYECTO / "data" / "referencia" / "poblacion.csv"
RUTA_CARTOGRAFIA = RAIZ_PROYECTO / "data" / "referencia" / "cartografia" / "municipios.geojson"
RUTA_CLAVE_HMAC = RAIZ_PROYECTO / "data" / "private" / "claves" / "hmac.key"

COLUMNAS_FECHA = [
    "FECHA_HECHO",
    "CASO_FECHA_DENUNCIA",
    "FECHA_CREACION",
    "CASO_FECHA_REG_NC",
    "FECHA_ASIGNACION",
    "CASO_FECHA_PRESCRIPCION",
    "FECHA_ULTIMA_ACTUACION",
    "FECHA_REGISTRO_ACTUACION",
]
PREFIJO_COLUMNA_FECHA = {
    "FECHA_HECHO": "fecha_hecho",
    "CASO_FECHA_DENUNCIA": "fecha_denuncia",
    "FECHA_CREACION": "fecha_creacion",
    "CASO_FECHA_REG_NC": "fecha_reg_nc",
    "FECHA_ASIGNACION": "fecha_asignacion",
    "CASO_FECHA_PRESCRIPCION": "fecha_prescripcion_declarada",
    "FECHA_ULTIMA_ACTUACION": "fecha_ultima_actuacion",
    "FECHA_REGISTRO_ACTUACION": "fecha_registro_actuacion",
}
# "FECHA_CREACION" (fecha_creacion) es la columna de referencia para los derivados ISO, la misma
# que usó I0 (CLAUDE.md §2.3): mide actividad registrada, no fecha del hecho.


def _cargar_divipola_entradas(
    ruta: Path,
) -> tuple[list[EntradaDivipola], dict[str, tuple[float, float]]]:
    df = pl.read_csv(ruta, infer_schema_length=0)
    entradas = [
        EntradaDivipola(f["cod_dpto"], f["cod_mpio"], f["departamento"], f["municipio"])
        for f in df.iter_rows(named=True)
    ]
    centroides = {
        f["cod_mpio"]: (float(f["lat_centroide"]), float(f["long_centroide"]))
        for f in df.iter_rows(named=True)
    }
    return entradas, centroides


@dataclass
class ResumenPlata:
    n_entrada: int
    n_cuarentena: int
    n_fuera_alcance: int
    n_registros_limpios: int
    valores_excluidos_alcance: dict[str, int]


def procesar_plata(
    conexion: duckdb.DuckDBPyConnection,
    lote_id: str,
    run_id: str,
    ruta_clave_hmac: Path = RUTA_CLAVE_HMAC,
) -> ResumenPlata:
    df_bronce = conexion.sql(
        "SELECT * FROM bronce.casos_raw WHERE lote_id = ?", params=[lote_id]
    ).pl()
    n_entrada = df_bronce.height

    contrato = cargar_contrato()
    resultado_validacion = validar_tabla(df_bronce, "CASOS", contrato, lote_id)
    escribir_cuarentena(conexion, resultado_validacion.cuarentena)
    assert conciliar(n_entrada, resultado_validacion.n_validas, resultado_validacion.n_cuarentena)

    df_validas = df_bronce.filter(
        pl.col("registro_uid").is_in(resultado_validacion.registros_uid_validos)
    )
    filas_validas = df_validas.to_dicts()

    alcance_cfg = cargar_yaml(RUTA_ALCANCE)
    filas_en_alcance, resumen_alcance = filtrar_por_alcance(
        filas_validas, alcance_cfg["columna"], set(alcance_cfg["valores_incluidos"])
    )

    reglas_fechas = cargar_yaml(RUTA_REGLAS_FECHAS)
    valores_invalidos_conocidos = set(reglas_fechas.get("valores_invalidos_conocidos", []))
    columnas_fecha_normalizadas = {
        columna: normalizar_columna_fecha(
            columna,
            [f.get(columna) for f in filas_en_alcance],
            valores_invalidos_conocidos,
        )
        for columna in COLUMNAS_FECHA
    }

    divipola_entradas, centroides = _cargar_divipola_entradas(RUTA_DIVIPOLA)
    excepciones_manuales = cargar_excepciones_manuales(cargar_yaml(RUTA_TERRITORIO_MANUAL))
    geometrias = cargar_geometrias_municipios(RUTA_CARTOGRAFIA)
    clave_hmac = obtener_o_crear_clave(ruta_clave_hmac)

    filas_limpias: list[dict[str, Any]] = []
    delitos_normalizados = []
    for i, fila in enumerate(filas_en_alcance):
        fila_limpia: dict[str, Any] = {
            "registro_uid": fila["registro_uid"],
            "lote_id": lote_id,
            "run_id": run_id,
        }

        descompuesto = descomponer_caso_noticia(fila.get("CASO_NOTICIA"))
        fila_limpia.update(
            {
                "caso_notica": descompuesto.valor_limpio,
                "caso_notica_valida_21": descompuesto.valido_21_digitos,
                "cn_dane": descompuesto.cn_dane,
                "cn_entidad": descompuesto.cn_entidad,
                "cn_unidad": descompuesto.cn_unidad,
                "cn_anio": descompuesto.cn_anio,
                "cn_consecutivo": descompuesto.cn_consecutivo,
                "caso_id": limpiar_identificador(fila.get("CASO_ID")),
                "desp_id": limpiar_identificador(fila.get("DESP_ID")),
            }
        )

        for columna, prefijo in PREFIJO_COLUMNA_FECHA.items():
            normalizada = columnas_fecha_normalizadas[columna]
            fila_limpia[prefijo] = normalizada.valores[i]
            fila_limpia[f"{prefijo}_valida"] = normalizada.fecha_valida[i]
            fila_limpia[f"{prefijo}_imputada"] = normalizada.fecha_imputada[i]
            fila_limpia[f"{prefijo}_motivo"] = normalizada.motivo[i]

        resultado_hechos = emparejar_con_manual(
            fila.get("DEPARTAMENTO_HECHOS"), fila.get("MUNICIPIO_HECHOS"),
            divipola_entradas, excepciones_manuales,
        )
        resultado_unidad = emparejar_con_manual(
            fila.get("DEPARTAMENTO_UNIDAD"), fila.get("MUNICIPIO_UNIDAD"),
            divipola_entradas, excepciones_manuales,
        )
        fila_limpia.update(
            {
                "cod_dpto_hechos": resultado_hechos.cod_dpto,
                "cod_mpio_hechos": resultado_hechos.cod_mpio,
                "metodo_mapeo_hechos": resultado_hechos.metodo,
                "confianza_mapeo_hechos": resultado_hechos.confianza,
                "cod_dpto_unidad": resultado_unidad.cod_dpto,
                "cod_mpio_unidad": resultado_unidad.cod_mpio,
                "metodo_mapeo_unidad": resultado_unidad.metodo,
                "confianza_mapeo_unidad": resultado_unidad.confianza,
            }
        )

        cod_mpio_hechos = resultado_hechos.cod_mpio
        centroide_hechos = centroides.get(cod_mpio_hechos) if cod_mpio_hechos else None
        coord = clasificar_coordenada(
            fila.get("LAT_DIR_HECHOS"), fila.get("LONG_DIR_HECHOS"),
            cod_mpio_hechos, centroide_hechos, geometrias,
        )
        fila_limpia.update(
            {
                "lat_hechos": coord.lat,
                "long_hechos": coord.long,
                "calidad_coord_hechos": coord.calidad_coord,
            }
        )

        delito_norm = normalizar_delito(
            fila.get("DELITO"), fila.get("TITULO"), fila.get("CAPITULO")
        )
        delitos_normalizados.append(delito_norm)
        fila_limpia.update(
            {
                "delito_nombre": delito_norm.delito_nombre,
                "articulo_cp": delito_norm.articulo_cp,
                "cuantia": delito_norm.cuantia,
                "delito_parseable": delito_norm.parseable,
            }
        )

        categoricas_norm = normalizar_fila_categoricas(fila)
        for columna, valor in categoricas_norm.items():
            fila_limpia[f"{columna.lower()}_orig"] = valor.valor_orig
            fila_limpia[f"{columna.lower()}_norm"] = valor.valor_normalizado

        fecha_hecho = fila_limpia["fecha_hecho"]
        componentes_ref = derivar_componentes_fecha(fila_limpia["fecha_creacion"])
        fila_limpia.update(
            {
                "dias_hecho_denuncia": dias_entre(fecha_hecho, fila_limpia["fecha_denuncia"]),
                "dias_denuncia_creacion": dias_entre(
                    fila_limpia["fecha_denuncia"], fila_limpia["fecha_creacion"]
                ),
                "dias_creacion_asignacion": dias_entre(
                    fila_limpia["fecha_creacion"], fila_limpia["fecha_asignacion"]
                ),
                "dias_hecho_prescripcion_declarada": dias_a_prescripcion_declarada(
                    fecha_hecho, fila_limpia["fecha_prescripcion_declarada"]
                ),
                "anio_iso_creacion": componentes_ref.anio_iso,
                "mes_creacion": componentes_ref.mes,
                "semana_iso_creacion": componentes_ref.semana_iso,
                "mismo_dpto_unidad_hechos": mismo_dpto_unidad_hechos(
                    resultado_hechos.cod_dpto, resultado_unidad.cod_dpto
                ),
                "mismo_mpio": mismo_mpio(resultado_hechos.cod_mpio, resultado_unidad.cod_mpio),
                "no_casos_conexos": fila.get("NO_CASOS_CONEXOS"),
            }
        )

        fila_limpia["numero_documento_token"] = seudonimizar(
            fila.get("NUMERO_DOCUMENTO"), clave_hmac
        )
        fila_limpia["fiscal_asignado_token"] = seudonimizar(
            fila.get("FISCAL_ASIGNADO_DESPACHO"), clave_hmac
        )
        fila_limpia["despacho"] = fila.get("DESPACHO")
        fila_limpia["competencia_despacho"] = fila.get("COMPETENCIA_DESPACHO")

        filas_limpias.append(fila_limpia)

    dim_delito = construir_dim_delito(delitos_normalizados)
    dim_despacho = _construir_dim_despacho(filas_en_alcance)
    dim_territorio = _construir_dim_territorio()
    dim_tiempo = _construir_dim_tiempo(filas_limpias)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", filas_limpias, modo="reemplazar")
    escribir_tabla_polars(conexion, "plata", "dim_delito", dim_delito, modo="reemplazar")
    escribir_tabla_polars(conexion, "plata", "dim_territorio", dim_territorio, modo="reemplazar")
    escribir_tabla_polars(conexion, "plata", "dim_tiempo", dim_tiempo, modo="reemplazar")
    escribir_tabla_polars(conexion, "plata", "dim_despacho", dim_despacho, modo="reemplazar")
    _escribir_reporte_calidad(
        conexion, lote_id, run_id, resultado_validacion, resumen_alcance,
        columnas_fecha_normalizadas, filas_limpias,
    )

    return ResumenPlata(
        n_entrada=n_entrada,
        n_cuarentena=resultado_validacion.n_cuarentena,
        n_fuera_alcance=resumen_alcance.n_fuera_alcance,
        n_registros_limpios=len(filas_limpias),
        valores_excluidos_alcance=resumen_alcance.valores_excluidos,
    )


def _construir_dim_territorio() -> list[dict[str, Any]]:
    divipola = pl.read_csv(RUTA_DIVIPOLA, infer_schema_length=0)
    poblacion = pl.read_csv(RUTA_POBLACION, infer_schema_length=0).with_columns(
        pl.col("anio").cast(pl.Int64),
        pl.col("poblacion_total").cast(pl.Float64),
    )
    combinado = poblacion.join(
        divipola.select(["cod_mpio", "lat_centroide", "long_centroide"]), on="cod_mpio", how="left"
    )
    return combinado.to_dicts()


def _construir_dim_tiempo(filas_limpias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fechas_validas = [
        f["fecha_creacion"] for f in filas_limpias if f.get("fecha_creacion") is not None
    ]
    if not fechas_validas:
        return []
    inicio, fin = min(fechas_validas), max(fechas_validas)
    filas = []
    actual = date(inicio.year, 1, 1)
    limite = date(fin.year, 12, 31)
    while actual <= limite:
        anio_iso, semana_iso, _ = actual.isocalendar()
        filas.append(
            {
                "fecha": actual,
                "anio": actual.year,
                "mes": actual.month,
                "dia": actual.day,
                "trimestre": (actual.month - 1) // 3 + 1,
                "semana_iso": semana_iso,
                "anio_iso": anio_iso,
                "es_fin_de_semana": actual.weekday() >= 5,
            }
        )
        actual += timedelta(days=1)
    return filas


def _construir_dim_despacho(filas_en_alcance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vistos: dict[str, dict[str, Any]] = {}
    for fila in filas_en_alcance:
        desp_id = limpiar_identificador(fila.get("DESP_ID"))
        if not desp_id or desp_id in vistos:
            continue
        vistos[desp_id] = {
            "desp_id": desp_id,
            "despacho": fila.get("DESPACHO"),
            "competencia_despacho": fila.get("COMPETENCIA_DESPACHO"),
        }
    return list(vistos.values())


def _escribir_reporte_calidad(
    conexion: duckdb.DuckDBPyConnection,
    lote_id: str,
    run_id: str,
    resultado_validacion: Any,
    resumen_alcance: Any,
    columnas_fecha_normalizadas: dict[str, Any],
    filas_limpias: list[dict[str, Any]],
) -> None:
    def _fila(categoria: str, clave: str, valor: object) -> dict[str, str]:
        return {
            "lote_id": lote_id,
            "run_id": run_id,
            "categoria": categoria,
            "clave": clave,
            "valor": str(valor),
        }

    filas_reporte: list[dict[str, str]] = [
        _fila("conciliacion", "n_cuarentena", resultado_validacion.n_cuarentena),
        _fila("conciliacion", "n_fuera_alcance", resumen_alcance.n_fuera_alcance),
        _fila("conciliacion", "n_registros_limpios", len(filas_limpias)),
    ]
    for valor_excluido, conteo in resumen_alcance.valores_excluidos.items():
        filas_reporte.append(_fila("alcance_excluido", valor_excluido, conteo))

    for columna, normalizada in columnas_fecha_normalizadas.items():
        n_imputadas = sum(normalizada.fecha_imputada)
        n_invalidas = sum(1 for v in normalizada.fecha_valida if not v) - n_imputadas
        filas_reporte.append(_fila("fechas_imputadas", columna, n_imputadas))
        filas_reporte.append(_fila("fechas_invalidas", columna, n_invalidas))

    conteo_territorio = Counter(f["metodo_mapeo_hechos"] for f in filas_limpias)
    for metodo, n in conteo_territorio.items():
        filas_reporte.append(_fila("territorio_metodo_hechos", metodo, n))

    conteo_coord = Counter(f["calidad_coord_hechos"] for f in filas_limpias)
    for calidad, n in conteo_coord.items():
        filas_reporte.append(_fila("calidad_coord_hechos", calidad, n))

    n_delito_no_parseable = sum(1 for f in filas_limpias if not f["delito_parseable"])
    filas_reporte.append(_fila("delito", "no_parseable", n_delito_no_parseable))

    conexion.execute("CREATE SCHEMA IF NOT EXISTS plata")
    conexion.execute(
        "CREATE TABLE IF NOT EXISTS plata.reporte_calidad "
        "(lote_id VARCHAR, run_id VARCHAR, categoria VARCHAR, clave VARCHAR, valor VARCHAR)"
    )
    df = pl.DataFrame(filas_reporte)
    conexion.register("_reporte_df", df)
    conexion.execute("INSERT INTO plata.reporte_calidad SELECT * FROM _reporte_df")
    conexion.unregister("_reporte_df")
