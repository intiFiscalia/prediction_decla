"""Orquestador del Bloque 2A (plan_trabajo.md §6.1; CLAUDE.md §2.3-§2.4).

Aplica, en orden, normalización conservadora → segmentación → enmascaramiento → casi-duplicados
→ embeddings sobre `entidades.relato`, y escribe `texto.relato_procesado`, `texto.duplicados`
(DuckDB) y los vectores en `data/embeddings/<lote_id>/` (Parquet, versionados por
`version_modelo`, plan_trabajo.md §6.1 paso 9). No repite la reparación de mojibake (ya está
hecha en `entidades.relato`, I1 tarea 4): este módulo parte de ese texto.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import escribir_tabla_polars
from decla.texto.duplicados import construir_grupos_duplicados, detectar_casi_duplicados
from decla.texto.embeddings import calcular_embeddings_relato, escribir_embeddings_parquet
from decla.texto.enmascaramiento import enmascarar
from decla.texto.normalizacion_conservadora import normalizar_conservador
from decla.texto.segmentacion import segmentar

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_SEGMENTACION = RAIZ_PROYECTO / "config" / "diccionarios" / "segmentacion_estructura.yaml"
RUTA_EMBEDDINGS_CONFIG = RAIZ_PROYECTO / "config" / "embeddings.yaml"
RUTA_EMBEDDINGS_DATOS_DEFECTO = RAIZ_PROYECTO / "data" / "embeddings"

UMBRAL_MAYUSCULAS_SOSTENIDAS = 0.6
MIN_LETRAS_PARA_EVALUAR_MAYUSCULAS = 20


def _es_mayusculas_sostenida(texto: str | None) -> bool:
    if not texto:
        return False
    letras = [c for c in texto if c.isalpha()]
    if len(letras) < MIN_LETRAS_PARA_EVALUAR_MAYUSCULAS:
        return False
    proporcion = sum(1 for c in letras if c.isupper()) / len(letras)
    return proporcion >= UMBRAL_MAYUSCULAS_SOSTENIDAS


@dataclass
class ResumenTexto:
    n_relatos: int
    n_relatos_en_grupo_duplicado: int
    n_grupos_duplicados: int
    n_con_contexto_denuncia: int
    version_modelo_embeddings: str


def _procesar_fila(fila: dict[str, Any], marcadores_descripcion_hecho: list[str]) -> dict[str, Any]:
    texto_original = fila.get("relato")
    texto_normalizado, _ = normalizar_conservador(texto_original)
    texto_normalizado = texto_normalizado or ""

    segmentacion = segmentar(texto_normalizado, marcadores_descripcion_hecho)
    enmascarado_completo = enmascarar(texto_normalizado)
    enmascarado_hecho = enmascarar(segmentacion.descripcion_hecho)

    return {
        "registro_uid": fila["registro_uid"],
        "caso_notica": fila.get("caso_notica"),
        "relato_normalizado": texto_normalizado,
        "relato_enmascarado": enmascarado_completo.texto_enmascarado,
        "contexto_denuncia": segmentacion.contexto_denuncia,
        "descripcion_hecho": segmentacion.descripcion_hecho,
        "descripcion_hecho_enmascarada": enmascarado_hecho.texto_enmascarado,
        "metodo_segmentacion": segmentacion.metodo,
        "es_mayusculas_sostenida": _es_mayusculas_sostenida(texto_original),
        "conteos_enmascaramiento": json.dumps(
            enmascarado_completo.conteos_por_tipo, ensure_ascii=False
        ),
    }


def procesar_texto(
    conexion: duckdb.DuckDBPyConnection,
    lote_id: str,
    run_id: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DATOS_DEFECTO,
) -> ResumenTexto:
    filas_relato = conexion.sql("SELECT * FROM entidades.relato").pl().to_dicts()

    config_segmentacion = cargar_yaml(RUTA_SEGMENTACION)
    marcadores = config_segmentacion.get("marcadores_descripcion_hecho", [])

    filas_procesadas = [_procesar_fila(fila, marcadores) for fila in filas_relato]

    textos_para_duplicados = {
        fila["registro_uid"]: fila["relato_enmascarado"]
        for fila in filas_procesadas
        if fila["relato_enmascarado"]
    }
    pares_duplicados = detectar_casi_duplicados(textos_para_duplicados)
    grupos = construir_grupos_duplicados(pares_duplicados)

    config_embeddings = cargar_yaml(RUTA_EMBEDDINGS_CONFIG)
    modelo_defecto = config_embeddings["modelo_defecto"]

    embeddings_relato = []
    embeddings_segmento = []
    for fila in filas_procesadas:
        embeddings_relato.extend(
            calcular_embeddings_relato(
                fila["registro_uid"], fila["relato_enmascarado"], modelo_defecto
            )
        )
        embeddings_segmento.extend(
            calcular_embeddings_relato(
                fila["registro_uid"], fila["descripcion_hecho_enmascarada"], modelo_defecto
            )
        )

    directorio_lote = ruta_embeddings_datos / lote_id
    escribir_embeddings_parquet(embeddings_relato, directorio_lote / "relato.parquet")
    escribir_embeddings_parquet(embeddings_segmento, directorio_lote / "segmento.parquet")

    filas_relato_procesado = [
        {**fila, "lote_id": lote_id, "run_id": run_id} for fila in filas_procesadas
    ]
    filas_duplicados = [
        {
            "registro_uid": registro_uid,
            "grupo_duplicado_id": grupo_id,
            "lote_id": lote_id,
            "run_id": run_id,
        }
        for registro_uid, grupo_id in grupos.items()
    ]

    escribir_tabla_polars(conexion, "texto", "relato_procesado", filas_relato_procesado)
    escribir_tabla_polars(conexion, "texto", "duplicados", filas_duplicados)

    return ResumenTexto(
        n_relatos=len(filas_procesadas),
        n_relatos_en_grupo_duplicado=len(grupos),
        n_grupos_duplicados=len(set(grupos.values())),
        n_con_contexto_denuncia=sum(
            1 for fila in filas_procesadas if fila["contexto_denuncia"] is not None
        ),
        version_modelo_embeddings=modelo_defecto,
    )
