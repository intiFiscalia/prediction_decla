"""Muestra estratificada de relatos para lectura humana (plan_trabajo.md Fase 1.9).

Escribe en `data/private/` (nunca en `reports/agregados/`): texto reparado y enmascarado
parcialmente (documento/teléfono/correo/placa), pero **no** con enmascaramiento de nombres propios
(eso requiere NER, Fase 4). Claude Code nunca abre esta salida.
"""

from __future__ import annotations

import html
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from decla.calidad.relatos import enmascarar_basico, reparar_mojibake, tiene_mojibake

N_MUESTRA_DEFECTO = 300


@dataclass
class FilaMuestra:
    relato_id: str
    caso_noticia: str
    anio: int | None
    departamento: str | None
    delito: str | None
    longitud_palabras: int
    texto_mostrado: str


def _bucket_longitud(longitud_palabras: int) -> str:
    if longitud_palabras < 200:
        return "corto"
    if longitud_palabras < 800:
        return "medio"
    return "largo"


def _anio_de_fecha_creacion(fecha_creacion: str | None) -> int | None:
    if not fecha_creacion:
        return None
    partes = fecha_creacion.split("/")
    if len(partes) == 3 and partes[2].isdigit():
        return int(partes[2])
    return None


def construir_muestra(
    filas_casos: list[dict[str, str | None]],
    filas_relatos: list[dict[str, str | None]],
    n: int = N_MUESTRA_DEFECTO,
    semilla: int = 20260131,
) -> list[FilaMuestra]:
    rng = random.Random(semilla)
    meta_por_noticia = {f["CASO_NOTICIA"]: f for f in filas_casos if f.get("CASO_NOTICIA")}

    por_estrato: dict[tuple, list[tuple]] = defaultdict(list)
    for idx, fila in enumerate(filas_relatos):
        caso_noticia = fila.get("CASO_NOTICIA")
        relato = fila.get("RELATO")
        if not caso_noticia or not relato:
            continue
        meta = meta_por_noticia.get(caso_noticia, {})
        anio = _anio_de_fecha_creacion(meta.get("FECHA_CREACION"))
        departamento = meta.get("DEPARTAMENTO_HECHOS")
        delito = meta.get("DELITO")
        longitud_palabras = len(relato.split())
        clave = (anio, departamento, delito, _bucket_longitud(longitud_palabras))
        candidato = (idx, caso_noticia, anio, departamento, delito, longitud_palabras, relato)
        por_estrato[clave].append(candidato)

    n_candidatos = sum(len(v) for v in por_estrato.values())
    objetivo = min(n, n_candidatos)
    seleccionados: list[tuple] = []
    estratos = [lista for lista in por_estrato.values() if lista]
    for lista in estratos:
        rng.shuffle(lista)

    while len(seleccionados) < objetivo and estratos:
        for lista in list(estratos):
            if len(seleccionados) >= objetivo:
                break
            seleccionados.append(lista.pop())
        estratos = [lista for lista in estratos if lista]

    resultado = []
    for idx, caso_noticia, anio, departamento, delito, longitud_palabras, relato in seleccionados:
        texto_reparado = reparar_mojibake(relato) if tiene_mojibake(relato) else relato
        texto_mostrado = enmascarar_basico(texto_reparado or relato)
        resultado.append(
            FilaMuestra(
                relato_id=f"MUESTRA-{idx:05d}",
                caso_noticia=caso_noticia,
                anio=anio,
                departamento=departamento,
                delito=delito,
                longitud_palabras=longitud_palabras,
                texto_mostrado=texto_mostrado,
            )
        )
    return resultado


def escribir_muestra_html(muestra: list[FilaMuestra], ruta: Path) -> None:
    partes = [
        "<html><head><meta charset='utf-8'><title>Muestra de lectura humana</title></head><body>",
        "<p><strong>Aviso:</strong> texto reparado (mojibake) y enmascarado parcialmente "
        "(documento/teléfono/correo/placa). Los nombres propios NO están enmascarados todavía "
        "(eso requiere NER, Fase 4). No compartir fuera del equipo autorizado.</p>",
    ]
    for fila in muestra:
        encabezado = f"{fila.relato_id} — año {fila.anio} — {fila.departamento} — {fila.delito}"
        partes.append(f"<hr><p><em>{html.escape(encabezado)}</em></p>")
        partes.append(f"<p>{html.escape(fila.texto_mostrado)}</p>")
    partes.append("</body></html>")

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(partes), encoding="utf-8")


def escribir_formulario_anotacion(muestra: list[FilaMuestra], ruta: Path) -> None:
    filas = [
        {
            "relato_id": f.relato_id,
            "caso_noticia": f.caso_noticia,
            "anio": f.anio,
            "departamento": f.departamento,
            "delito": f.delito,
            "fenomeno_anotado": "",
            "mecanismo_anotado": "",
            "sector_anotado": "",
            "notas": "",
        }
        for f in muestra
    ]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(filas).write_csv(ruta)
