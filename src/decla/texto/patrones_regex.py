"""Patrones por reglas sobre RELATO (plan_trabajo.md §6.1 paso 5; CLAUDE.md §4.20-§4.22).

Cada función busca un tipo de patrón y devuelve evidencia literal con posición (`inicio`, `fin`
en el texto que recibe) para poder citarlo y, si corresponde, proyectarlo al original vía
`texto.offsets`. No se "corrige" el contenido (CLAUDE.md §4.22: "la limpieza no debe corregir
contenido sustantivo"): un monto o una fecha mal escrita se reporta como se encontró, con su
`valor_normalizado` como mejor esfuerzo, nunca reemplazando el texto evidencia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

MESES_CANONICOS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

UMBRAL_FUZZY_MES = 75


@dataclass(frozen=True)
class Coincidencia:
    categoria: str
    texto_evidencia: str
    inicio: int
    fin: int
    valor_normalizado: str | None = None


def _coincidencias(patron: re.Pattern[str], texto: str, categoria: str) -> list[Coincidencia]:
    return [
        Coincidencia(categoria, m.group(), m.start(), m.end())
        for m in patron.finditer(texto)
    ]


PATRON_ARTICULO_PENAL = re.compile(r"\bart(?:[íi]culos?)?\.?\s*(\d{1,4})\b", re.IGNORECASE)


def extraer_articulos_penales(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia(
            "articulo_penal", m.group(), m.start(), m.end(), valor_normalizado=m.group(1)
        )
        for m in PATRON_ARTICULO_PENAL.finditer(texto)
    ]


PATRON_MONTO_CIFRA = re.compile(
    r"(?:\$|USD|US\$)\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?(?:\s?(?:millones|mill\.?|mil))?",
    re.IGNORECASE,
)

_PALABRAS_NUMERICAS = (
    r"(?:un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|veinte|treinta|"
    r"cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|cientos|mil|mill[oó]n|"
    r"millones)"
)
PATRON_MONTO_EN_LETRAS = re.compile(
    rf"\b{_PALABRAS_NUMERICAS}(?:\s+{_PALABRAS_NUMERICAS}){{0,5}}\s+de\s+(?:pesos|d[oó]lares)\b",
    re.IGNORECASE,
)


def extraer_montos(texto: str) -> list[Coincidencia]:
    return _coincidencias(PATRON_MONTO_CIFRA, texto, "monto") + _coincidencias(
        PATRON_MONTO_EN_LETRAS, texto, "monto"
    )


PATRON_PLACA_VEHICULO = re.compile(r"\b[A-Za-z]{3}[-\s]?\d{3}\b")
PATRON_PLACA_MOTO = re.compile(r"\b[A-Za-z]{3}[-\s]?\d{2}[A-Za-z]\b")


def extraer_placas(texto: str) -> list[Coincidencia]:
    return _coincidencias(PATRON_PLACA_VEHICULO, texto, "placa") + _coincidencias(
        PATRON_PLACA_MOTO, texto, "placa"
    )


PATRON_CEDULA = re.compile(
    r"\b(?:c[eé]dula(?:\s+de\s+(?:ciudadan[íi]a|extranjer[íi]a))?|c\.?\s?c\.?|c\.?\s?e\.?)\s*"
    r"(?:n[úu]mero|no\.?|#)?\s*:?\s*(\d{1,3}(?:[.,]\d{3}){1,3}|\d{6,10})\b",
    re.IGNORECASE,
)


def extraer_cedulas(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia("cedula", m.group(), m.start(), m.end(), valor_normalizado=m.group(1))
        for m in PATRON_CEDULA.finditer(texto)
    ]


PATRON_NIT = re.compile(r"\bNIT\.?\s*:?\s*(\d{6,10})[-.\s]?(\d)\b", re.IGNORECASE)


def extraer_nit(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia(
            "nit", m.group(), m.start(), m.end(), valor_normalizado=f"{m.group(1)}-{m.group(2)}"
        )
        for m in PATRON_NIT.finditer(texto)
    ]


PATRON_TELEFONO_MOVIL = re.compile(r"\b(?:\+?57\s?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}\b")
PATRON_TELEFONO_FIJO_CON_DISPARADOR = re.compile(
    r"\b(?:tel[eé]fono|celular|cel\.?)\s*:?\s*(\(?\d{1,3}\)?[\s.-]?\d{7})\b", re.IGNORECASE
)


def extraer_telefonos(texto: str) -> list[Coincidencia]:
    return _coincidencias(PATRON_TELEFONO_MOVIL, texto, "telefono") + [
        Coincidencia("telefono", m.group(), m.start(), m.end(), valor_normalizado=m.group(1))
        for m in PATRON_TELEFONO_FIJO_CON_DISPARADOR.finditer(texto)
    ]


PATRON_CORREO = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def extraer_correos(texto: str) -> list[Coincidencia]:
    return _coincidencias(PATRON_CORREO, texto, "correo")


PATRON_MOTOR_CHASIS = re.compile(
    r"\b(motor|chasis)\s*(?:n[úu]mero|no\.?|#)?\s*:?\s*([A-Za-z0-9]{5,17})\b", re.IGNORECASE
)


def extraer_motor_chasis(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia(
            m.group(1).lower(), m.group(), m.start(), m.end(), valor_normalizado=m.group(2)
        )
        for m in PATRON_MOTOR_CHASIS.finditer(texto)
    ]


PATRON_KM_VIA = re.compile(r"\bk(?:il[oó]metro|m)\.?\s*(\d{1,3}(?:\+\d{1,3})?)\b", re.IGNORECASE)


def extraer_km_via(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia("km_via", m.group(), m.start(), m.end(), valor_normalizado=m.group(1))
        for m in PATRON_KM_VIA.finditer(texto)
    ]


PATRON_SUBPARTIDA = re.compile(
    r"\bsubpartida(?:\s+arancelaria)?\s*(?:n[úu]mero|no\.?)?\s*:?\s*"
    r"(\d{2,4}(?:[.\s]?\d{2,4}){1,3})\b",
    re.IGNORECASE,
)


def extraer_subpartidas(texto: str) -> list[Coincidencia]:
    return [
        Coincidencia("subpartida", m.group(), m.start(), m.end(), valor_normalizado=m.group(1))
        for m in PATRON_SUBPARTIDA.finditer(texto)
    ]


PATRON_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
PATRON_FECHA_MES_TEXTO_BARRA = re.compile(r"\b(\d{1,2})/([A-Za-zÁÉÍÓÚáéíóúñÑ]+)/(\d{4})\b")
PATRON_FECHA_MES_TEXTO_DE = re.compile(
    r"\b(\d{1,2})\s+DE\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s+DEL?\s+(\d{4})\b", re.IGNORECASE
)


def _mes_normalizado(token: str) -> str | None:
    resultado = process.extractOne(token.lower(), MESES_CANONICOS, scorer=fuzz.ratio)
    if resultado is None or resultado[1] < UMBRAL_FUZZY_MES:
        return None
    return resultado[0]


def extraer_fechas_en_texto(texto: str) -> list[Coincidencia]:
    coincidencias = _coincidencias(PATRON_FECHA_NUMERICA, texto, "fecha_texto")
    for patron in (PATRON_FECHA_MES_TEXTO_BARRA, PATRON_FECHA_MES_TEXTO_DE):
        for m in patron.finditer(texto):
            mes = _mes_normalizado(m.group(2))
            if mes is None:
                continue
            coincidencias.append(
                Coincidencia(
                    "fecha_texto",
                    m.group(),
                    m.start(),
                    m.end(),
                    valor_normalizado=f"{m.group(1)} de {mes} de {m.group(3)}",
                )
            )
    return coincidencias


def extraer_todas(texto: str) -> list[Coincidencia]:
    return (
        extraer_articulos_penales(texto)
        + extraer_montos(texto)
        + extraer_placas(texto)
        + extraer_cedulas(texto)
        + extraer_nit(texto)
        + extraer_telefonos(texto)
        + extraer_correos(texto)
        + extraer_motor_chasis(texto)
        + extraer_km_via(texto)
        + extraer_subpartidas(texto)
        + extraer_fechas_en_texto(texto)
    )
