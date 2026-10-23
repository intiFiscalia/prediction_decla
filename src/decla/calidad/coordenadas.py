"""Reparación y clasificación de coordenadas (CLAUDE.md §4.17; plan_trabajo.md Fase 1.5).

Sin cartografía real (`data/referencia/` vacío), la validación espacial se reduce a la caja de
Colombia y a la comparación con el centroide municipal declarado: es un sustituto de
punto-en-polígono, no el punto-en-polígono fino que llegará con shapefiles reales (I1/I3).
"""

from __future__ import annotations

from dataclasses import dataclass

CAJA_COLOMBIA = {"lat_min": -4.3, "lat_max": 13.6, "long_min": -82.0, "long_max": -66.0}
_ETIQUETAS = ("LAT", "LONG", "LON")


@dataclass
class ResultadoCoordenada:
    lat_original: str | None
    long_original: str | None
    lat_reparada: float | None
    long_reparada: float | None
    metodo: str  # vacia | correcta | reparada_escala | invertida | fuera_de_caja | no_reparable
    coincide_centroide: bool | None = None


def _en_caja(lat: float, lon: float) -> bool:
    return (
        CAJA_COLOMBIA["lat_min"] <= lat <= CAJA_COLOMBIA["lat_max"]
        and CAJA_COLOMBIA["long_min"] <= lon <= CAJA_COLOMBIA["long_max"]
    )


def _extraer_numero_con_etiqueta(valor: str) -> float | None:
    texto = valor.strip().upper()
    for etiqueta in _ETIQUETAS:
        if texto.startswith(etiqueta):
            texto = texto[len(etiqueta) :].strip()
            break
    try:
        return float(texto)
    except ValueError:
        return None


def _reescalar_a_caja(
    valor: float, minimo: float, maximo: float, maximas_potencias: int = 6
) -> float | None:
    for k in range(maximas_potencias + 1):
        candidato = valor / (10**k)
        if minimo <= candidato <= maximo:
            return candidato
    return None


def reparar_coordenadas(
    lat_texto: str | None,
    long_texto: str | None,
    centroide: tuple[float, float] | None = None,
) -> ResultadoCoordenada:
    if not lat_texto and not long_texto:
        return ResultadoCoordenada(lat_texto, long_texto, None, None, metodo="vacia")

    lat_num = _extraer_numero_con_etiqueta(lat_texto) if lat_texto else None
    long_num = _extraer_numero_con_etiqueta(long_texto) if long_texto else None
    if lat_num is None or long_num is None:
        return ResultadoCoordenada(lat_texto, long_texto, None, None, metodo="no_reparable")

    tiene_punto = "." in (lat_texto or "") and "." in (long_texto or "")

    if tiene_punto:
        if _en_caja(lat_num, long_num):
            metodo, lat_final, long_final = "correcta", lat_num, long_num
        elif _en_caja(long_num, lat_num):
            metodo, lat_final, long_final = "invertida", long_num, lat_num
        else:
            return ResultadoCoordenada(
                lat_texto, long_texto, lat_num, long_num, metodo="fuera_de_caja"
            )
    else:
        lat_r = _reescalar_a_caja(lat_num, CAJA_COLOMBIA["lat_min"], CAJA_COLOMBIA["lat_max"])
        long_r = _reescalar_a_caja(long_num, CAJA_COLOMBIA["long_min"], CAJA_COLOMBIA["long_max"])
        if lat_r is None or long_r is None:
            return ResultadoCoordenada(lat_texto, long_texto, None, None, metodo="no_reparable")
        metodo, lat_final, long_final = "reparada_escala", lat_r, long_r

    coincide_centroide = None
    if centroide is not None:
        coincide_centroide = (
            abs(lat_final - centroide[0]) < 0.01 and abs(long_final - centroide[1]) < 0.01
        )

    return ResultadoCoordenada(
        lat_texto, long_texto, lat_final, long_final, metodo=metodo,
        coincide_centroide=coincide_centroide,
    )
