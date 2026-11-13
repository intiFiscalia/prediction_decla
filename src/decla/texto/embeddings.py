"""Embeddings por relato y por segmento (plan_trabajo.md §6.1 paso 9, §5.2; CLAUDE.md §4.20).

Fragmenta por oraciones (spaCy) respetando el límite real de tokens de cada modelo
(`model.max_seq_length`: 128 para mpnet, 512 para e5-base, 8192 para bge-m3 — nunca un límite fijo
hardcodeado, plan_trabajo.md §5.2). Un relato más largo que el límite se parte en fragmentos que
nunca cortan una oración a la mitad; se codifica cada uno y se agregan por MEDIA y por MÁXIMO —
ambas se guardan, porque cuál es mejor "es una decisión que se evalúa en la Fase 4" con datos, no
antes (plan_trabajo.md §6.1 paso 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl
from sentence_transformers import SentenceTransformer

from decla.comun.entorno import configurar_entorno_offline, verificar_hash_modelo
from decla.texto.pipeline_spacy import analizar

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_MODELOS = RAIZ_PROYECTO / "models"

# intfloat/multilingual-e5-base requiere los prefijos "query:"/"passage:" (plan_trabajo.md §5.2).
PREFIJO_PASAJE_POR_MODELO: dict[str, str] = {"multilingual-e5-base": "passage: "}
PREFIJO_CONSULTA_POR_MODELO: dict[str, str] = {"multilingual-e5-base": "query: "}

MEDIA = "media"
MAXIMO = "maximo"

_modelos_cacheados: dict[str, SentenceTransformer] = {}


def cargar_modelo_embeddings(nombre_modelo: str) -> SentenceTransformer:
    if nombre_modelo not in _modelos_cacheados:
        configurar_entorno_offline()
        verificar_hash_modelo(nombre_modelo)
        _modelos_cacheados[nombre_modelo] = SentenceTransformer(str(RUTA_MODELOS / nombre_modelo))
    return _modelos_cacheados[nombre_modelo]


def _oraciones(texto: str) -> list[str]:
    doc = analizar(texto)
    oraciones = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    return oraciones or ([texto.strip()] if texto.strip() else [])


def fragmentar_por_limite(texto: str, modelo: SentenceTransformer) -> list[str]:
    oraciones = _oraciones(texto)
    limite = modelo.max_seq_length or 512
    fragmentos: list[str] = []
    actual: list[str] = []
    for oracion in oraciones:
        candidato = " ".join([*actual, oracion])
        # `add_special_tokens=True` cuenta los tokens especiales (p. ej. <s>/</s>) que el propio
        # `modelo.encode()` agrega después: contar sin ellos subestima y deja pasar fragmentos
        # que exceden `max_seq_length` en tiempo de codificación real.
        n_tokens = len(modelo.tokenizer.encode(candidato, add_special_tokens=True))
        if n_tokens <= limite or not actual:
            actual.append(oracion)
        else:
            fragmentos.append(" ".join(actual))
            actual = [oracion]
    if actual:
        fragmentos.append(" ".join(actual))
    return fragmentos


@dataclass(frozen=True)
class EmbeddingRelato:
    registro_uid: str
    version_modelo: str
    agregacion: str
    vector: list[float]


@dataclass(frozen=True)
class FragmentoEmbedding:
    texto: str
    vector: list[float]


def calcular_vectores_fragmentos(texto: str | None, nombre_modelo: str) -> list[FragmentoEmbedding]:
    """Embedding de cada fragmento (grupo de oraciones que respeta `max_seq_length`) por
    separado, sin agregar — usado para construir MEDIA y MÁXIMO (abajo), donde agrupar oraciones
    hasta el límite de tokens es una optimización razonable de eficiencia para un embedding de
    documento completo.
    """
    if not texto or not texto.strip():
        return []

    modelo = cargar_modelo_embeddings(nombre_modelo)
    fragmentos = fragmentar_por_limite(texto, modelo)
    prefijo = PREFIJO_PASAJE_POR_MODELO.get(nombre_modelo, "")
    vectores = modelo.encode([prefijo + f for f in fragmentos], convert_to_numpy=True)
    return [FragmentoEmbedding(f, v.tolist()) for f, v in zip(fragmentos, vectores, strict=True)]


def calcular_vectores_oraciones(texto: str | None, nombre_modelo: str) -> list[FragmentoEmbedding]:
    """Embedding de cada ORACIÓN por separado (sin agrupar varias en un fragmento, a diferencia
    de `calcular_vectores_fragmentos`). Para comparar contra un vocabulario de categorías
    (decla.conocimiento.zero_shot, decla.conocimiento.sectores) agrupar oraciones diluye una
    mención puntual (p. ej. una sola oración que describe un mecanismo específico) con la oración
    vecina de trámite genérico — agrupar por `max_seq_length` no evita esa dilución, solo la
    hace menos predecible. El modelo trunca internamente oraciones más largas que su límite de
    tokens (comportamiento normal de `SentenceTransformer.encode`).
    """
    if not texto or not texto.strip():
        return []

    modelo = cargar_modelo_embeddings(nombre_modelo)
    oraciones = _oraciones(texto)
    prefijo = PREFIJO_PASAJE_POR_MODELO.get(nombre_modelo, "")
    vectores = modelo.encode([prefijo + o for o in oraciones], convert_to_numpy=True)
    return [FragmentoEmbedding(o, v.tolist()) for o, v in zip(oraciones, vectores, strict=True)]


def calcular_embeddings_relato(
    registro_uid: str, texto: str | None, nombre_modelo: str
) -> list[EmbeddingRelato]:
    fragmentos = calcular_vectores_fragmentos(texto, nombre_modelo)
    if not fragmentos:
        return []

    vectores = np.array([f.vector for f in fragmentos])
    return [
        EmbeddingRelato(registro_uid, nombre_modelo, MEDIA, vectores.mean(axis=0).tolist()),
        EmbeddingRelato(registro_uid, nombre_modelo, MAXIMO, vectores.max(axis=0).tolist()),
    ]


def escribir_embeddings_parquet(embeddings: list[EmbeddingRelato], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        [
            {
                "registro_uid": e.registro_uid,
                "version_modelo": e.version_modelo,
                "agregacion": e.agregacion,
                "vector": e.vector,
            }
            for e in embeddings
        ]
    )
    df.write_parquet(ruta)
