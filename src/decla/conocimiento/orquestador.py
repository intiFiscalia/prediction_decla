"""Orquestador del Bloque 2B (plan_trabajo.md Fase 5; CLAUDE.md §2.3-§2.4).

Aplica, sobre `texto.relato_procesado`: reglas de 2A (patrones_regex) → NER institución/lugar
(2A, pipeline_spacy) → negación (2A) → sector CIIU (explícito→inferido→indeterminado) →
mecanismo (explícito→zero-shot→no_clasificado, mismo patrón que sector desde 2026-11-06), y
escribe `texto.menciones`. El sector y el mecanismo se asignan siempre al relato
(`registro_uid`), nunca a una persona u organización.

El diccionario explícito de mecanismo (`config/diccionarios/mecanismos_expresiones.yaml`) nunca
sustituye al modelo como vía de descubrimiento: solo acelera y hace exacta la coincidencia de lo
que el diccionario ya anticipa; todo lo que no coincide sigue dependiendo del modelo zero-shot,
que puede seguir señalando mecanismos nuevos no listados (como candidato de baja confianza a
revisar), nunca "quemados" a la lista de 12 códigos semilla.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import escribir_tabla_polars
from decla.conocimiento.menciones import (
    ORIGEN_EXPLICITO_REGLA,
    ORIGEN_INFERIDO_MODELO,
    Mencion,
    calcular_mencion_id,
    coincidencias_a_menciones,
)
from decla.conocimiento.sectores import (
    SECTOR_INDETERMINADO,
    ClasificacionSector,
    calcular_vectores_ciiu,
    cargar_ciiu,
    cargar_expresiones,
    cargar_jerarquia_division_seccion,
    clasificar_sector_explicito,
    clasificar_sector_inferido,
)
from decla.conocimiento.zero_shot import (
    NO_CLASIFICADO,
    ClasificacionZeroShot,
    calcular_vectores_vocabulario,
    cargar_expresiones_mecanismo,
    cargar_vocabulario,
    clasificar_fragmento,
    clasificar_mecanismo_explicito,
)
from decla.texto.negacion import AFIRMADA, clasificar_polaridad
from decla.texto.patrones_regex import extraer_todas
from decla.texto.pipeline_spacy import analizar

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_NEGACION = RAIZ_PROYECTO / "config" / "diccionarios" / "negacion_marcadores.yaml"
RUTA_EMBEDDINGS_CONFIG = RAIZ_PROYECTO / "config" / "embeddings.yaml"
RUTA_UMBRALES = RAIZ_PROYECTO / "config" / "umbrales.yaml"

EXTRACTOR_NER = "pipeline_spacy"
VERSION_EXTRACTOR_NER = "1"
EXTRACTOR_ZERO_SHOT = "zero_shot_embeddings"
VERSION_EXTRACTOR_ZERO_SHOT = "1"
EXTRACTOR_DICCIONARIO_MECANISMO = "diccionario_mecanismo"
VERSION_EXTRACTOR_DICCIONARIO_MECANISMO = "1"

ETIQUETAS_NER_A_CATEGORIA = {"INSTITUCION": "institucion", "LOC": "lugar"}


@dataclass
class ResumenConocimiento:
    n_relatos: int
    n_menciones: int
    n_menciones_por_categoria: dict[str, int]
    n_sector_explicito: int
    n_sector_inferido: int
    n_sector_indeterminado: int
    n_sector_sin_texto: int
    n_mecanismo_explicito: int
    n_mecanismo_inferido: int
    n_mecanismo_indeterminado: int


def _menciones_desde_patrones(
    texto: str, registro_uid: str, run_id: str, segmento: str, disparadores: dict[str, Any]
) -> list[Mencion]:
    coincidencias = extraer_todas(texto)
    ventana = disparadores.get("ventana_tokens", 8)
    polaridad_por_indice = {
        i: clasificar_polaridad(
            texto,
            c.inicio,
            c.fin,
            disparadores.get("disparadores_negacion", []),
            disparadores.get("disparadores_hipotesis", []),
            disparadores.get("disparadores_atribucion", []),
            ventana,
        )
        for i, c in enumerate(coincidencias)
    }
    return coincidencias_a_menciones(
        coincidencias, registro_uid, run_id, segmento, polaridad_por_indice
    )


def _menciones_desde_ner(
    texto: str, registro_uid: str, run_id: str, segmento: str
) -> list[Mencion]:
    doc = analizar(texto)
    menciones = []
    for ent in doc.ents:
        categoria = ETIQUETAS_NER_A_CATEGORIA.get(ent.label_)
        if categoria is None:
            continue
        menciones.append(
            Mencion(
                mencion_id=calcular_mencion_id(
                    registro_uid, categoria, None, ent.start_char, ent.end_char, EXTRACTOR_NER
                ),
                registro_uid=registro_uid,
                run_id=run_id,
                categoria=categoria,
                subcategoria=None,
                valor_normalizado=ent.text,
                texto_evidencia=ent.text,
                inicio=ent.start_char,
                fin=ent.end_char,
                segmento=segmento,
                origen=ORIGEN_EXPLICITO_REGLA,
                polaridad=AFIRMADA,
                confianza=1.0,
                extractor=EXTRACTOR_NER,
                version_extractor=VERSION_EXTRACTOR_NER,
            )
        )
    return menciones


def _mencion_sector(
    texto: str,
    registro_uid: str,
    run_id: str,
    segmento: str,
    expresiones: list[dict[str, str]],
    jerarquia: dict[str, str],
    vectores_ciiu: dict[str, list[float]],
    nombre_modelo: str,
    confianza_minima: float,
    margen_minimo_top2: float,
) -> Mencion | None:
    if not texto or not texto.strip():
        return None

    resultado: ClasificacionSector | None = clasificar_sector_explicito(
        texto, expresiones, jerarquia
    )
    if resultado is None:
        resultado = clasificar_sector_inferido(
            texto, vectores_ciiu, nombre_modelo, jerarquia, confianza_minima, margen_minimo_top2
        )

    inicio, fin = 0, len(texto)
    return Mencion(
        mencion_id=calcular_mencion_id(registro_uid, "sector", None, inicio, fin, resultado.origen),
        registro_uid=registro_uid,
        run_id=run_id,
        categoria="sector",
        subcategoria=resultado.seccion,
        valor_normalizado=resultado.code,
        texto_evidencia=resultado.texto_evidencia or texto[:200],
        inicio=inicio,
        fin=fin,
        segmento=segmento,
        origen=resultado.origen,
        polaridad=AFIRMADA,
        confianza=resultado.confianza,
        extractor="sectores_ciiu",
        version_extractor="1",
    )


def _mencion_mecanismo(
    texto: str,
    registro_uid: str,
    run_id: str,
    segmento: str,
    expresiones_mecanismo: list[dict[str, str]],
    vectores_vocabulario: dict[str, list[float]],
    nombre_modelo: str,
    confianza_minima: float,
    margen_minimo_top2: float,
) -> Mencion | None:
    if not texto or not texto.strip():
        return None

    explicito = clasificar_mecanismo_explicito(texto, expresiones_mecanismo)
    if explicito is not None:
        inicio, fin = 0, len(texto)
        return Mencion(
            mencion_id=calcular_mencion_id(
                registro_uid, "mecanismo", None, inicio, fin, EXTRACTOR_DICCIONARIO_MECANISMO
            ),
            registro_uid=registro_uid,
            run_id=run_id,
            categoria="mecanismo",
            subcategoria=None,
            valor_normalizado=explicito.codigo,
            texto_evidencia=explicito.texto_evidencia,
            inicio=inicio,
            fin=fin,
            segmento=segmento,
            origen=ORIGEN_EXPLICITO_REGLA,
            polaridad=AFIRMADA,
            confianza=1.0,
            extractor=EXTRACTOR_DICCIONARIO_MECANISMO,
            version_extractor=VERSION_EXTRACTOR_DICCIONARIO_MECANISMO,
        )

    # Nada en el diccionario explícito coincidió: se deja la puerta abierta al modelo, nunca se
    # fuerza "no_clasificado" solo porque el diccionario no lo anticipó (el modelo puede seguir
    # señalando un mecanismo de los 12 semilla, o quedar como candidato de baja confianza a
    # revisar si de verdad es un mecanismo nuevo).
    resultado: ClasificacionZeroShot = clasificar_fragmento(
        texto, vectores_vocabulario, nombre_modelo, confianza_minima, margen_minimo_top2
    )
    if resultado.codigo is None:
        return None

    inicio, fin = 0, len(texto)
    valor = None if resultado.codigo == NO_CLASIFICADO else resultado.codigo
    return Mencion(
        mencion_id=calcular_mencion_id(
            registro_uid, "mecanismo", None, inicio, fin, EXTRACTOR_ZERO_SHOT
        ),
        registro_uid=registro_uid,
        run_id=run_id,
        categoria="mecanismo",
        subcategoria=None,
        valor_normalizado=valor,
        texto_evidencia=resultado.texto_evidencia or texto[:200],
        inicio=inicio,
        fin=fin,
        segmento=segmento,
        origen=ORIGEN_INFERIDO_MODELO,
        polaridad=AFIRMADA,
        confianza=resultado.confianza,
        extractor=EXTRACTOR_ZERO_SHOT,
        version_extractor=VERSION_EXTRACTOR_ZERO_SHOT,
    )


def procesar_conocimiento(
    conexion: duckdb.DuckDBPyConnection, run_id: str
) -> ResumenConocimiento:
    filas = conexion.sql(
        "SELECT registro_uid, relato_enmascarado, descripcion_hecho_enmascarada "
        "FROM texto.relato_procesado"
    ).pl().to_dicts()

    disparadores = cargar_yaml(RUTA_NEGACION)
    umbrales = cargar_yaml(RUTA_UMBRALES)
    nombre_modelo = cargar_yaml(RUTA_EMBEDDINGS_CONFIG)["modelo_defecto"]

    jerarquia = cargar_jerarquia_division_seccion()
    expresiones = cargar_expresiones()
    expresiones_mecanismo = cargar_expresiones_mecanismo()
    vectores_ciiu = calcular_vectores_ciiu(cargar_ciiu(), nombre_modelo)
    vectores_mecanismo = calcular_vectores_vocabulario(
        cargar_vocabulario("mecanismo"), nombre_modelo
    )

    umbrales_sector = umbrales["sector_inferido"]
    umbrales_mecanismo = umbrales["zero_shot_mecanismo"]

    todas_las_menciones: list[Mencion] = []
    n_sector_explicito = n_sector_inferido = n_sector_indeterminado = n_sector_sin_texto = 0
    n_mecanismo_explicito = n_mecanismo_inferido = n_mecanismo_indeterminado = 0

    for fila in filas:
        texto_completo = fila.get("relato_enmascarado") or ""
        texto_hecho = fila.get("descripcion_hecho_enmascarada") or texto_completo
        registro_uid = fila["registro_uid"]

        if texto_completo:
            todas_las_menciones.extend(
                _menciones_desde_patrones(
                    texto_completo, registro_uid, run_id, "descripcion_hecho", disparadores
                )
            )
            todas_las_menciones.extend(
                _menciones_desde_ner(texto_completo, registro_uid, run_id, "descripcion_hecho")
            )

        mencion_sector = _mencion_sector(
            texto_hecho,
            registro_uid,
            run_id,
            "descripcion_hecho",
            expresiones,
            jerarquia,
            vectores_ciiu,
            nombre_modelo,
            umbrales_sector["confianza_minima"],
            umbrales_sector["margen_minimo_top2"],
        )
        if mencion_sector is None:
            n_sector_sin_texto += 1
        else:
            todas_las_menciones.append(mencion_sector)
            if mencion_sector.origen == ORIGEN_EXPLICITO_REGLA:
                n_sector_explicito += 1
            elif mencion_sector.valor_normalizado == SECTOR_INDETERMINADO:
                n_sector_indeterminado += 1
            else:
                n_sector_inferido += 1

        mencion_mecanismo = _mencion_mecanismo(
            texto_hecho,
            registro_uid,
            run_id,
            "descripcion_hecho",
            expresiones_mecanismo,
            vectores_mecanismo,
            nombre_modelo,
            umbrales_mecanismo["confianza_minima"],
            umbrales_mecanismo["margen_minimo_top2"],
        )
        if mencion_mecanismo is not None:
            todas_las_menciones.append(mencion_mecanismo)
            if mencion_mecanismo.origen == ORIGEN_EXPLICITO_REGLA:
                n_mecanismo_explicito += 1
            elif mencion_mecanismo.valor_normalizado is None:
                n_mecanismo_indeterminado += 1
            else:
                n_mecanismo_inferido += 1

    filas_menciones = [
        {
            "mencion_id": m.mencion_id,
            "registro_uid": m.registro_uid,
            "run_id": m.run_id,
            "categoria": m.categoria,
            "subcategoria": m.subcategoria,
            "valor_normalizado": m.valor_normalizado,
            "texto_evidencia": m.texto_evidencia,
            "inicio": m.inicio,
            "fin": m.fin,
            "segmento": m.segmento,
            "origen": m.origen,
            "polaridad": m.polaridad,
            "confianza": m.confianza,
            "extractor": m.extractor,
            "version_extractor": m.version_extractor,
            "estado_revision": m.estado_revision,
            "revisor": m.revisor,
            "fecha_revision": m.fecha_revision,
        }
        for m in todas_las_menciones
    ]
    escribir_tabla_polars(conexion, "texto", "menciones", filas_menciones)

    n_por_categoria: dict[str, int] = {}
    for m in todas_las_menciones:
        n_por_categoria[m.categoria] = n_por_categoria.get(m.categoria, 0) + 1

    return ResumenConocimiento(
        n_relatos=len(filas),
        n_menciones=len(todas_las_menciones),
        n_menciones_por_categoria=n_por_categoria,
        n_sector_explicito=n_sector_explicito,
        n_sector_inferido=n_sector_inferido,
        n_sector_indeterminado=n_sector_indeterminado,
        n_sector_sin_texto=n_sector_sin_texto,
        n_mecanismo_explicito=n_mecanismo_explicito,
        n_mecanismo_inferido=n_mecanismo_inferido,
        n_mecanismo_indeterminado=n_mecanismo_indeterminado,
    )
