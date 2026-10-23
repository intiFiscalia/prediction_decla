"""Perfil de calidad de RELATO (CLAUDE.md §4.15, §4.20, §4.22, §4.24; Fase 1.7).

Cubre longitud, mojibake cirílico y verificación de que su reparación no deja residuo, mayúsculas
sostenidas, indicios de truncamiento, casi-duplicados entre noticias distintas (MinHash) y conteo
—nunca texto— de patrones de datos personales. `enmascarar_basico` solo cubre identificadores
detectables por regex (documento, teléfono, correo, placa); el enmascaramiento de nombres propios
con NER es de Fase 4, no de este diagnóstico.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from datasketch import MinHash, MinHashLSH

_PATRON_CIRILICO = re.compile(r"[Ѐ-ӿ]")

PATRONES_PERSONALES = {
    "cedula": re.compile(r"\bC\.?C\.?\s*\d{6,10}\b", re.IGNORECASE),
    "cedula_extranjera": re.compile(r"\bC\.?E\.?\s*\d{6,10}\b", re.IGNORECASE),
    "telefono": re.compile(r"\b3\d{9}\b"),
    "correo": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "placa": re.compile(r"\b[A-Z]{3}\d{2,3}[A-Z]?\b"),
}


# --------------------------------------------------------------------------------------
# Longitud
# --------------------------------------------------------------------------------------


@dataclass
class PerfilLongitud:
    n_relatos: int
    n_vacios: int
    percentiles_caracteres: dict[int, float] = field(default_factory=dict)
    percentiles_palabras: dict[int, float] = field(default_factory=dict)


def _percentiles(valores: list[int], puntos: tuple[int, ...]) -> dict[int, float]:
    if not valores:
        return dict.fromkeys(puntos, 0.0)
    if len(valores) < 2:
        return dict.fromkeys(puntos, float(valores[0]))
    cortes = statistics.quantiles(valores, n=100, method="inclusive")
    return {p: float(cortes[p - 1]) for p in puntos}


def perfil_longitud(
    relatos: list[str | None], puntos: tuple[int, ...] = (10, 25, 50, 75, 90, 99)
) -> PerfilLongitud:
    no_nulos = [r for r in relatos if r]
    return PerfilLongitud(
        n_relatos=len(relatos),
        n_vacios=len(relatos) - len(no_nulos),
        percentiles_caracteres=_percentiles(sorted(len(r) for r in no_nulos), puntos),
        percentiles_palabras=_percentiles(sorted(len(r.split()) for r in no_nulos), puntos),
    )


# --------------------------------------------------------------------------------------
# Mojibake
# --------------------------------------------------------------------------------------


def tiene_mojibake(texto: str | None) -> bool:
    return bool(texto) and bool(_PATRON_CIRILICO.search(texto or ""))


def reparar_mojibake(texto: str) -> str | None:
    try:
        return texto.encode("cp1251").decode("cp1252")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None


@dataclass
class ResultadoReparacionMojibake:
    reparado: str | None
    sin_residuo: bool
    fallo_reparacion: bool


def verificar_reparacion_mojibake(texto: str) -> ResultadoReparacionMojibake:
    reparado = reparar_mojibake(texto)
    if reparado is None:
        return ResultadoReparacionMojibake(reparado=None, sin_residuo=False, fallo_reparacion=True)
    return ResultadoReparacionMojibake(
        reparado=reparado, sin_residuo=not tiene_mojibake(reparado), fallo_reparacion=False
    )


# --------------------------------------------------------------------------------------
# Mayúsculas sostenidas y truncamiento
# --------------------------------------------------------------------------------------


def es_mayuscula_sostenida(texto: str, umbral: float = 0.8) -> bool:
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return False
    mayusculas = sum(1 for c in letras if c.isupper())
    return (mayusculas / len(letras)) >= umbral


@dataclass
class ResumenTruncamiento:
    longitud_maxima: int
    n_en_maximo: int
    pct_en_maximo: float
    posible_truncamiento: bool


def detectar_posible_truncamiento(
    longitudes: list[int], tolerancia: int = 5, umbral_fraccion: float = 0.05
) -> ResumenTruncamiento:
    if not longitudes:
        return ResumenTruncamiento(0, 0, 0.0, False)
    maximo = max(longitudes)
    n_en_maximo = sum(1 for longitud in longitudes if maximo - longitud <= tolerancia)
    fraccion = n_en_maximo / len(longitudes)
    return ResumenTruncamiento(
        longitud_maxima=maximo,
        n_en_maximo=n_en_maximo,
        pct_en_maximo=round(fraccion * 100, 2),
        posible_truncamiento=fraccion >= umbral_fraccion,
    )


# --------------------------------------------------------------------------------------
# Datos personales (solo conteo; el enmascaramiento con NER es de Fase 4)
# --------------------------------------------------------------------------------------


def contar_patrones_personales(texto: str) -> dict[str, int]:
    return {nombre: len(patron.findall(texto)) for nombre, patron in PATRONES_PERSONALES.items()}


def enmascarar_basico(texto: str) -> str:
    resultado = texto
    resultado = PATRONES_PERSONALES["correo"].sub("[CORREO]", resultado)
    resultado = PATRONES_PERSONALES["cedula_extranjera"].sub("[DOC]", resultado)
    resultado = PATRONES_PERSONALES["cedula"].sub("[DOC]", resultado)
    resultado = PATRONES_PERSONALES["telefono"].sub("[TELEFONO]", resultado)
    resultado = PATRONES_PERSONALES["placa"].sub("[PLACA]", resultado)
    return resultado


# --------------------------------------------------------------------------------------
# Casi-duplicados entre noticias distintas (MinHash/LSH)
# --------------------------------------------------------------------------------------


def _shingles_de_palabras(texto: str, k: int = 3) -> set[str]:
    palabras = texto.split()
    if len(palabras) < k:
        return {" ".join(palabras)} if palabras else set()
    return {" ".join(palabras[i : i + k]) for i in range(len(palabras) - k + 1)}


def _minhash_de_texto(texto: str, num_perm: int) -> MinHash:
    firma = MinHash(num_perm=num_perm)
    for shingle in _shingles_de_palabras(texto):
        firma.update(shingle.encode("utf-8"))
    return firma


@dataclass
class ParCasiDuplicado:
    id_a: str
    id_b: str
    caso_noticia_a: str
    caso_noticia_b: str


def detectar_casi_duplicados_entre_noticias(
    relatos: list[tuple[str, str, str]],
    umbral: float = 0.8,
    num_perm: int = 128,
) -> list[ParCasiDuplicado]:
    """`relatos` es una lista de (relato_id, caso_noticia, texto). Solo reporta pares cuyo
    `caso_noticia` difiere: el mismo hecho contado dos veces en la misma noticia no cuenta
    como casi-duplicado entre noticias (CLAUDE.md §4.21, Fase 4 técnica de MinHash).
    """
    lsh = MinHashLSH(threshold=umbral, num_perm=num_perm)
    minhashes: dict[str, MinHash] = {}
    id_a_noticia: dict[str, str] = {}

    for relato_id, caso_noticia, texto in relatos:
        firma = _minhash_de_texto(texto, num_perm)
        minhashes[relato_id] = firma
        id_a_noticia[relato_id] = caso_noticia
        lsh.insert(relato_id, firma)

    vistos: set[tuple[str, str]] = set()
    pares: list[ParCasiDuplicado] = []
    for relato_id, caso_noticia, _texto in relatos:
        for otro_id in lsh.query(minhashes[relato_id]):
            if otro_id == relato_id or id_a_noticia[otro_id] == caso_noticia:
                continue
            clave = tuple(sorted((relato_id, otro_id)))
            if clave in vistos:
                continue
            vistos.add(clave)
            pares.append(
                ParCasiDuplicado(clave[0], clave[1], id_a_noticia[clave[0]], id_a_noticia[clave[1]])
            )
    return pares
