"""Cardinalidad, grano y unión CASOS↔RELATOS (CLAUDE.md §4.3, §4.10; plan_trabajo.md Fase 1.2).

No decide el grano por sí solo: calcula evidencia numérica y propone 2–3 hipótesis rankeadas para
que la persona decida en la compuerta de I0.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from decla.ingesta.lectores import TablaLeida

CAMPOS_DIFERENCIADORES_MULTIDELITO = ["DELITO", "DESPACHO", "FECHA_ASIGNACION", "ULTIMA_ACTUACION"]
_PATRON_SOLO_DIGITOS = re.compile(r"^\d+$")


@dataclass
class ResumenCardinalidad:
    n_filas: int
    n_caso_id_unicos: int
    n_caso_noticia_unicos: int
    n_pares_unicos: int
    n_duplicados_exactos: int
    n_duplicados_parciales: int
    distribucion_filas_por_noticia: dict[int, int] = field(default_factory=dict)


@dataclass
class ResumenUnion:
    n_noticias_casos: int
    n_noticias_relatos: int
    n_coincidencias: int
    n_huerfanos_relatos: int
    n_casos_sin_relato: int
    pct_cobertura_casos: float
    pct_cobertura_relatos: float
    distribucion_relatos_por_noticia: dict[int, int] = field(default_factory=dict)


@dataclass
class ResumenCasoNoticia:
    n_total: int
    n_longitud_21: int
    pct_longitud_21: float
    n_prefijo_dane_valido: int
    pct_prefijo_dane_valido: float
    n_anio_coincide: int
    pct_anio_coincide: float


@dataclass
class HipotesisGrano:
    nombre: str
    evidencia: str
    puntaje: float


def resumir_cardinalidad(tabla: TablaLeida) -> ResumenCardinalidad:
    filas = tabla.filas
    caso_ids = [f.get("CASO_ID") for f in filas if f.get("CASO_ID")]
    caso_noticias = [f.get("CASO_NOTICIA") for f in filas if f.get("CASO_NOTICIA")]
    pares = [(f.get("CASO_ID"), f.get("CASO_NOTICIA")) for f in filas]

    firmas = [tuple(sorted(f.items())) for f in filas]
    conteo_firmas = Counter(firmas)
    n_duplicados_exactos = sum(c - 1 for c in conteo_firmas.values() if c > 1)

    por_noticia: dict[str, list[dict]] = defaultdict(list)
    for f in filas:
        cn = f.get("CASO_NOTICIA")
        if cn:
            por_noticia[cn].append(f)

    n_clusters_parciales = 0
    for grupo in por_noticia.values():
        if len(grupo) < 2:
            continue
        difiere = any(
            len({g.get(campo) for g in grupo}) > 1 for campo in CAMPOS_DIFERENCIADORES_MULTIDELITO
        )
        if difiere:
            n_clusters_parciales += 1

    distribucion = Counter(len(g) for g in por_noticia.values())

    return ResumenCardinalidad(
        n_filas=len(filas),
        n_caso_id_unicos=len(set(caso_ids)),
        n_caso_noticia_unicos=len(set(caso_noticias)),
        n_pares_unicos=len(set(pares)),
        n_duplicados_exactos=n_duplicados_exactos,
        n_duplicados_parciales=n_clusters_parciales,
        distribucion_filas_por_noticia=dict(distribucion),
    )


def resumir_union(tabla_casos: TablaLeida, tabla_relatos: TablaLeida) -> ResumenUnion:
    noticias_casos = {f.get("CASO_NOTICIA") for f in tabla_casos.filas if f.get("CASO_NOTICIA")}
    noticias_relatos_por_fila = [
        f.get("CASO_NOTICIA") for f in tabla_relatos.filas if f.get("CASO_NOTICIA")
    ]
    noticias_relatos = set(noticias_relatos_por_fila)

    coincidencias = noticias_casos & noticias_relatos
    huerfanos_relatos = noticias_relatos - noticias_casos
    casos_sin_relato = noticias_casos - noticias_relatos

    distribucion = Counter(Counter(noticias_relatos_por_fila).values())
    n_relatos = len(noticias_relatos_por_fila)
    n_relatos_con_match = sum(1 for cn in noticias_relatos_por_fila if cn in noticias_casos)

    return ResumenUnion(
        n_noticias_casos=len(noticias_casos),
        n_noticias_relatos=len(noticias_relatos),
        n_coincidencias=len(coincidencias),
        n_huerfanos_relatos=len(huerfanos_relatos),
        n_casos_sin_relato=len(casos_sin_relato),
        pct_cobertura_casos=(
            round(len(coincidencias) / len(noticias_casos) * 100, 2) if noticias_casos else 0.0
        ),
        pct_cobertura_relatos=(
            round(n_relatos_con_match / n_relatos * 100, 2) if n_relatos else 0.0
        ),
        distribucion_relatos_por_noticia=dict(distribucion),
    )


def _extraer_anio(fecha_texto: str | None) -> str | None:
    if not fecha_texto:
        return None
    partes = fecha_texto.split("/")
    if len(partes) != 3:
        return None
    anio = partes[2]
    return anio if len(anio) == 4 and anio.isdigit() else None


def verificar_hipotesis_caso_noticia(
    tabla_casos: TablaLeida, cod_mpios_validos: set[str]
) -> ResumenCasoNoticia:
    """Hipótesis a validar (CLAUDE.md §4.10): CASO_NOTICIA = cod_mpio(5) + entidad(2) +
    unidad_receptora(5) + año(4) + consecutivo(5). Solo se usa como verificación de
    consistencia, no para derivar municipio/año de forma definitiva.
    """
    candidatos: list[tuple[str, str | None]] = [
        (valor, f.get("FECHA_CREACION"))
        for f in tabla_casos.filas
        if (valor := f.get("CASO_NOTICIA"))
    ]

    n_total = len(candidatos)
    n_longitud_21 = 0
    n_prefijo_valido = 0
    n_anio_coincide = 0

    for valor, fecha_creacion in candidatos:
        valor_limpio = valor[:-2] if valor.endswith(".0") else valor
        if not _PATRON_SOLO_DIGITOS.match(valor_limpio) or len(valor_limpio) != 21:
            continue
        n_longitud_21 += 1
        if valor_limpio[:5] in cod_mpios_validos:
            n_prefijo_valido += 1
        anio_embebido = valor_limpio[12:16]
        if anio_embebido == _extraer_anio(fecha_creacion):
            n_anio_coincide += 1

    def _pct(n: int, base: int) -> float:
        return round(n / base * 100, 2) if base else 0.0

    return ResumenCasoNoticia(
        n_total=n_total,
        n_longitud_21=n_longitud_21,
        pct_longitud_21=_pct(n_longitud_21, n_total),
        n_prefijo_dane_valido=n_prefijo_valido,
        pct_prefijo_dane_valido=_pct(n_prefijo_valido, n_longitud_21),
        n_anio_coincide=n_anio_coincide,
        pct_anio_coincide=_pct(n_anio_coincide, n_longitud_21),
    )


def proponer_hipotesis_grano(resumen: ResumenCardinalidad) -> list[HipotesisGrano]:
    frac_notica_unica = resumen.n_caso_noticia_unicos / resumen.n_filas if resumen.n_filas else 0
    tasa_multidelito = (
        resumen.n_duplicados_parciales / resumen.n_caso_noticia_unicos
        if resumen.n_caso_noticia_unicos
        else 0
    )

    hipotesis = [
        HipotesisGrano(
            nombre="una fila = una noticia criminal",
            evidencia=(
                f"{resumen.n_caso_noticia_unicos} CASO_NOTICIA únicos de {resumen.n_filas} filas "
                f"({frac_notica_unica:.1%}); {resumen.n_duplicados_parciales} grupos de la misma "
                "noticia con DELITO/DESPACHO/fecha distintos sugieren que no es 1:1 estricto."
            ),
            puntaje=frac_notica_unica,
        ),
        HipotesisGrano(
            nombre="una fila = noticia × delito/diligencia",
            evidencia=(
                f"{resumen.n_duplicados_parciales} de {resumen.n_caso_noticia_unicos} noticias "
                f"({tasa_multidelito:.1%}) tienen más de una fila con DELITO/DESPACHO/fecha "
                "distintos: consistente con una fila por delito o actuación dentro de la misma "
                "noticia."
            ),
            puntaje=tasa_multidelito,
        ),
        HipotesisGrano(
            nombre="indeterminado / mezcla de unidades de registro",
            evidencia=(
                f"{resumen.n_duplicados_exactos} duplicados exactos; distribución de filas por "
                f"noticia: {resumen.distribucion_filas_por_noticia}."
            ),
            puntaje=0.0,
        ),
    ]
    return sorted(hipotesis, key=lambda h: h.puntaje, reverse=True)
