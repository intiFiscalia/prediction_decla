"""Congela `config/taxonomia/v1.0.yaml` a partir de las decisiones del taller de revisión
(`revision.decisiones_taxonomia`, plan_trabajo.md §7.2) y las fichas de
`fenomenos.grupos_descubiertos`.

Solo incluye un fenómeno en v1.0 si la **última** decisión registrada para su `grupo_id` es
`aprobar` (CLAUDE.md: "no presentes grupos no revisados como fenómenos"). `artefacto` y
`descartar` quedan excluidos pero documentados (trazabilidad); `dividir` y `fusionar` no se
resuelven solos — requieren una acción manual (reclusterizar o combinar ids) que todavía no
existe como código, así que se reportan como pendientes en vez de adivinar qué hacer.

A diferencia de `v0.1-borrador.yaml` (que incluye medoides/bordes de texto enmascarado real),
v1.0 solo guarda `ids_ejemplo` (registro_uid, ya seudonimizados por hash) — nunca texto — por lo
que SÍ se puede versionar en git (plan_trabajo.md §7.2: "ejemplos sintéticos o ids").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

DECISIONES_ESTADO = {"aprobar", "artefacto", "descartar", "dividir", "fusionar"}
DECISION_INCLUIR = "aprobar"
DECISIONES_EXCLUIR = {"artefacto", "descartar"}
DECISIONES_PENDIENTES = {"dividir", "fusionar"}


def _slug(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower()).strip("_")


def _fecha_de(fila: dict[str, Any]) -> datetime:
    valor = fila["fecha"]
    return valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor))


@dataclass(frozen=True)
class DecisionResuelta:
    grupo_id: str
    decision_final: str | None
    nombre_final: str | None
    calificador: str | None
    fecha: datetime | None


def resolver_decisiones(decisiones: list[dict[str, Any]]) -> dict[str, DecisionResuelta]:
    """Para cada `grupo_id`, toma la decisión de estado (aprobar/artefacto/descartar/dividir/
    fusionar) más reciente y, por separado, el nombre más reciente de un `renombrar` (son ejes
    independientes: un grupo puede aprobarse antes o después de que se le ponga nombre).
    """
    por_grupo: dict[str, list[dict[str, Any]]] = {}
    for fila in decisiones:
        por_grupo.setdefault(str(fila["grupo_id"]), []).append(fila)

    resueltas: dict[str, DecisionResuelta] = {}
    for grupo_id, filas in por_grupo.items():
        filas_estado = [f for f in filas if f["decision"] in DECISIONES_ESTADO]
        filas_nombre = [f for f in filas if f["decision"] == "renombrar"]

        ultima_estado = max(filas_estado, key=_fecha_de) if filas_estado else None
        ultima_nombre = max(filas_nombre, key=_fecha_de) if filas_nombre else None

        resueltas[grupo_id] = DecisionResuelta(
            grupo_id=grupo_id,
            decision_final=ultima_estado["decision"] if ultima_estado else None,
            nombre_final=str(ultima_nombre["nombre_nuevo"]) if ultima_nombre else None,
            calificador=str(ultima_estado["calificador"]) if ultima_estado else None,
            fecha=_fecha_de(ultima_estado) if ultima_estado else None,
        )
    return resueltas


@dataclass(frozen=True)
class ResultadoCongelamiento:
    fenomenos: list[dict[str, Any]] = field(default_factory=list)
    excluidos: list[dict[str, Any]] = field(default_factory=list)
    pendientes: list[dict[str, Any]] = field(default_factory=list)
    sin_decision: list[str] = field(default_factory=list)


def construir_taxonomia_v1(
    decisiones: list[dict[str, Any]], grupos: list[dict[str, Any]]
) -> ResultadoCongelamiento:
    resueltas = resolver_decisiones(decisiones)
    grupos_por_id = {str(g["grupo_id"]): g for g in grupos}

    fenomenos: list[dict[str, Any]] = []
    excluidos: list[dict[str, Any]] = []
    pendientes: list[dict[str, Any]] = []
    sin_decision: list[str] = []

    codigos_usados: set[str] = set()

    for grupo_id, grupo in grupos_por_id.items():
        resuelta = resueltas.get(grupo_id)
        if resuelta is None or resuelta.decision_final is None:
            sin_decision.append(grupo_id)
            continue

        if resuelta.decision_final in DECISIONES_PENDIENTES:
            pendientes.append(
                {
                    "grupo_id": grupo_id,
                    "decision": resuelta.decision_final,
                    "motivo": (
                        "requiere acción manual (reclusterizar o combinar ids) que todavía no "
                        "tiene código de soporte; no se resuelve automáticamente"
                    ),
                }
            )
            continue

        if resuelta.decision_final in DECISIONES_EXCLUIR:
            excluidos.append(
                {
                    "grupo_id": grupo_id,
                    "motivo": resuelta.decision_final,
                    "calificador": resuelta.calificador,
                    "fecha": resuelta.fecha.isoformat() if resuelta.fecha else None,
                }
            )
            continue

        nombre = resuelta.nombre_final or f"Grupo {grupo_id} (sin nombre asignado)"
        codigo_base = _slug(nombre) or f"grupo_{grupo_id}"
        codigo = codigo_base
        sufijo = 2
        while codigo in codigos_usados:
            codigo = f"{codigo_base}_{sufijo}"
            sufijo += 1
        codigos_usados.add(codigo)

        terminos_raw = grupo.get("terminos_c_tfidf") or ""
        terminos = [t.strip() for t in str(terminos_raw).split(",") if t.strip()]
        medoides_raw = grupo.get("medoides") or ""
        ids_ejemplo = [m.strip() for m in str(medoides_raw).split(",") if m.strip()]

        fenomenos.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "definicion": "pendiente_de_redaccion_por_analista",
                "nivel_jerarquico": 1,
                "delitos_relacionados": "pendiente_de_calculo",
                "terminos_dominantes": terminos,
                "ids_ejemplo": ids_ejemplo,
                "n_miembros": grupo.get("n_miembros"),
                "dominancia_plantilla": grupo.get("dominancia_plantilla"),
                "dominancia_unidad": grupo.get("dominancia_unidad"),
                "estado": "aprobado",
                "calificador": resuelta.calificador,
                "fecha_decision": resuelta.fecha.isoformat() if resuelta.fecha else None,
            }
        )

    return ResultadoCongelamiento(
        fenomenos=fenomenos, excluidos=excluidos, pendientes=pendientes, sin_decision=sin_decision
    )


def escribir_taxonomia_v1(resultado: ResultadoCongelamiento, ruta_salida: Path) -> None:
    contenido = {
        "version": "1.0",
        "nota": (
            "Taxonomía congelada a partir del taller de revisión humana "
            "(revision.decisiones_taxonomia). 'definicion' y 'delitos_relacionados' quedan "
            "pendientes de redacción manual por un analista: esta herramienta no inventa "
            "contenido que no fue decidido en el taller."
        ),
        "fenomenos": resultado.fenomenos,
        "excluidos": resultado.excluidos,
        "pendientes": resultado.pendientes,
        "grupos_sin_decision": resultado.sin_decision,
    }
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(
        yaml.safe_dump(contenido, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
