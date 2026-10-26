"""Carga de `es_core_news_lg` offline + EntityRuler con gazetteers (plan_trabajo.md §6.1
pasos 4-6; CLAUDE.md §2.2, §4.21).

El modelo se instala desde el wheel local declarado en `pyproject.toml`
(`[tool.uv.sources]`), nunca desde un índice remoto; antes de usarlo se verifica su hash contra
`models/MANIFEST.json` (`decla.comun.entorno.verificar_hash_modelo`) para detectar un archivo
corrupto o sustituido. El EntityRuler se agrega ANTES del NER estadístico (orden estándar de
spaCy): las entidades de los gazetteers (instituciones, tipos de documento, municipios y
departamentos DIVIPOLA) quedan fijadas y el NER estadístico solo completa lo que no cubrieron.

Etiquetas nuevas que no chocan con las de spaCy (PER, ORG, LOC, MISC): `INSTITUCION`,
`TIPO_DOCUMENTO`. Los nombres DIVIPOLA se etiquetan `LOC`, el mismo tipo semántico que ya usa el
NER general.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler

from decla.comun.configuracion import cargar_yaml
from decla.comun.entorno import configurar_entorno_offline, verificar_hash_modelo

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DIVIPOLA = RAIZ_PROYECTO / "data" / "referencia" / "divipola.csv"
RUTA_INSTITUCIONES = RAIZ_PROYECTO / "config" / "diccionarios" / "instituciones.yaml"
RUTA_TIPOS_DOCUMENTO = RAIZ_PROYECTO / "config" / "diccionarios" / "tipos_documento.yaml"
NOMBRE_MODELO = "es_core_news_lg"

_modelo_cacheado: Language | None = None


def _patrones_institucion(ruta: Path = RUTA_INSTITUCIONES) -> list[dict[str, Any]]:
    catalogo = cargar_yaml(ruta)
    return [
        {"label": "INSTITUCION", "pattern": variante}
        for entrada in catalogo.get("instituciones", [])
        for variante in entrada["variantes"]
    ]


def _patrones_tipo_documento(ruta: Path = RUTA_TIPOS_DOCUMENTO) -> list[dict[str, Any]]:
    catalogo = cargar_yaml(ruta)
    return [
        {"label": "TIPO_DOCUMENTO", "pattern": variante}
        for entrada in catalogo.get("tipos_documento", [])
        for variante in entrada["variantes"]
    ]


def _patrones_territorio(ruta: Path = RUTA_DIVIPOLA) -> list[dict[str, Any]]:
    if not ruta.exists():
        return []
    df = pl.read_csv(ruta, infer_schema_length=0)
    nombres = set(df["municipio"].drop_nulls().to_list()) | set(
        df["departamento"].drop_nulls().to_list()
    )
    return [{"label": "LOC", "pattern": nombre} for nombre in sorted(nombres) if nombre]


def construir_patrones_gazetteer() -> list[dict[str, Any]]:
    return _patrones_institucion() + _patrones_tipo_documento() + _patrones_territorio()


def cargar_modelo(nombre_modelo: str = NOMBRE_MODELO) -> Language:
    configurar_entorno_offline()
    verificar_hash_modelo(nombre_modelo)
    nlp = spacy.load(nombre_modelo)
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    assert isinstance(ruler, EntityRuler)
    ruler.add_patterns(construir_patrones_gazetteer())
    return nlp


def obtener_modelo_compartido() -> Language:
    """Carga el modelo una sola vez por proceso: `cargar_modelo` tarda segundos y se usa en
    cada relato del lote.
    """
    global _modelo_cacheado
    if _modelo_cacheado is None:
        _modelo_cacheado = cargar_modelo()
    return _modelo_cacheado


def analizar(texto: str) -> spacy.tokens.Doc:
    return obtener_modelo_compartido()(texto)
