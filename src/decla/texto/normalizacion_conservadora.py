"""Normalización conservadora de RELATO (plan_trabajo.md §6.1 paso 2; CLAUDE.md §4.21-§4.22).

No se eliminan tildes, números ni signos: solo se reconstruyen palabras partidas por salto de
línea, se unifican comillas y guiones, se colapsan espacios, y se baja a minúscula natural los
tramos en mayúsculas sostenidas (frecuentes en actas policiales) para que el matching de
gazetteers (insensible a mayúsculas) y los embeddings no traten "ACTA POLICIAL" distinto de
"acta policial" por pura casing.

Los dos primeros pasos (reunir palabras partidas, colapsar espacios) cambian la longitud del
texto y producen un `MapaOffsets` real; los otros dos (comillas/guiones, minúsculas sostenidas)
son sustituciones carácter a carácter que nunca mueven una posición, así que no necesitan mapa:
el mapa final es la composición de los dos pasos que sí cambian longitud.
"""

from __future__ import annotations

import re

from decla.texto.offsets import ConstructorTextoConOffsets, MapaOffsets, componer

PATRON_PALABRA_PARTIDA = re.compile(r"(\w)-\n[ \t]*(\w)", re.UNICODE)
PATRON_ESPACIOS = re.compile(r"\s+")

TABLA_COMILLAS_Y_GUIONES = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
        "‘": "'",
        "’": "'",
        "´": "'",
        "`": "'",
        "–": "-",
        "—": "-",
    }
)

MIN_PALABRAS_MAYUSCULAS_EN_RUN = 3


def _reunir_palabras_partidas(texto: str) -> tuple[str, MapaOffsets]:
    constructor = ConstructorTextoConOffsets()
    cursor = 0
    for coincidencia in PATRON_PALABRA_PARTIDA.finditer(texto):
        constructor.agregar(texto[cursor : coincidencia.start()], cursor, coincidencia.start())
        constructor.agregar(
            coincidencia.group(1) + coincidencia.group(2), coincidencia.start(), coincidencia.end()
        )
        cursor = coincidencia.end()
    constructor.agregar(texto[cursor:], cursor, len(texto))
    return constructor.construir()


def _unificar_comillas_y_guiones(texto: str) -> str:
    return texto.translate(TABLA_COMILLAS_Y_GUIONES)


def _colapsar_espacios(texto: str) -> tuple[str, MapaOffsets]:
    constructor = ConstructorTextoConOffsets()
    cursor = 0
    for coincidencia in PATRON_ESPACIOS.finditer(texto):
        constructor.agregar(texto[cursor : coincidencia.start()], cursor, coincidencia.start())
        constructor.agregar(" ", coincidencia.start(), coincidencia.end())
        cursor = coincidencia.end()
    constructor.agregar(texto[cursor:], cursor, len(texto))
    texto_final, mapa = constructor.construir()
    return texto_final.strip(), mapa


def _clasificar_palabra_mayuscula(palabra: str) -> bool | None:
    """True si la palabra es toda mayúscula, False si tiene alguna minúscula, None si no tiene
    letras (números, puntuación) y por lo tanto no aporta evidencia ni rompe una racha.
    """
    letras = [c for c in palabra if c.isalpha()]
    if not letras:
        return None
    return all(c.isupper() for c in letras)


def _bajar_mayusculas_sostenidas(texto: str) -> str:
    palabras = list(re.finditer(r"\S+", texto))
    clasificaciones = [_clasificar_palabra_mayuscula(p.group()) for p in palabras]

    resultado = list(texto)
    i = 0
    while i < len(palabras):
        if clasificaciones[i] is False:
            i += 1
            continue
        j = i
        n_mayusculas = 0
        while j < len(palabras) and clasificaciones[j] is not False:
            if clasificaciones[j] is True:
                n_mayusculas += 1
            j += 1
        if n_mayusculas >= MIN_PALABRAS_MAYUSCULAS_EN_RUN:
            inicio, fin = palabras[i].start(), palabras[j - 1].end()
            resultado[inicio:fin] = texto[inicio:fin].lower()
        i = j
    return "".join(resultado)


def normalizar_conservador(texto: str | None) -> tuple[str | None, MapaOffsets]:
    if texto is None:
        return None, MapaOffsets()

    texto_a, mapa_a = _reunir_palabras_partidas(texto)
    texto_b = _unificar_comillas_y_guiones(texto_a)
    texto_c, mapa_c = _colapsar_espacios(texto_b)
    texto_final = _bajar_mayusculas_sostenidas(texto_c)

    return texto_final, componer(mapa_a, mapa_c)
