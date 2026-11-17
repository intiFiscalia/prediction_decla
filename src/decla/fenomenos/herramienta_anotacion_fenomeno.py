"""Herramienta de anotación de fenómenos por relato completo (ADR 0024; plan_trabajo.md §7.3).
Distinta de `decla.conocimiento.herramienta_anotacion_menciones` (esa califica menciones
puntuales dentro del relato, Bloque 2B; esta califica el relato entero y es multietiqueta).

La calificación se guarda en `data/private/` (nunca la lee Claude Code); el resumen agregado
(cobertura por código y, con doble anotación, kappa de Cohen por código) se exporta a
`reports/agregados/i4/`. Mismo patrón de separación pura/interfaz que
`herramienta_anotacion_menciones.py`: estas funciones se prueban con fixtures sintéticos.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sklearn.metrics import cohen_kappa_score

CONFIRMADA = "confirmada"
CORREGIDA = "corregida"

RUIDO_ADMINISTRATIVO = "ruido_administrativo"
NO_CLASIFICADO = "no_clasificado"
CODIGOS_ANOTACION_EXTRA = (RUIDO_ADMINISTRATIVO, NO_CLASIFICADO)

# Descripción por código, igual criterio que `docs/fichas/guia_anotacion_fenomenos.md` (fuente de
# verdad del detalle). Incluye el caso límite de esa guía porque esta constante alimenta tanto el
# tooltip de la app de anotación como el prompt del clasificador LLM (ADR 0026) — ambos deben
# usar exactamente el mismo criterio que el analista humano, no uno aparte inventado para el LLM.
DESCRIPCION_CODIGO: dict[str, str] = {
    "lavado_de_activos_a_traves_de_empresas": (
        "Confirmar: el relato describe activos movidos o justificados a través de una o más "
        "empresas (facturación, aportes societarios, compras a nombre de la empresa) como parte "
        "del hecho investigado. Caso límite: una empresa mencionada solo como lugar de trabajo "
        "de una persona, sin que el relato la vincule al movimiento de activos, no basta para "
        "confirmar este código."
    ),
    "incautacion_y_conteo_de_efectivo": (
        "Confirmar: el relato describe el hallazgo, incautación o conteo de dinero en efectivo "
        "como parte del procedimiento narrado. Caso límite: una cifra de dinero mencionada solo "
        "como referencia (p. ej. el monto de una demanda civil citada de fondo) sin incautación "
        "o conteo real, no confirma este código."
    ),
    "organizacion_criminal": (
        "Confirmar: el relato describe una estructura con roles diferenciados (cabecillas, "
        "alias, logística) operando de forma coordinada, no solo una persona actuando sola. "
        "Caso límite: dos personas mencionadas sin descripción de estructura u organización "
        "entre ellas no alcanza para confirmar este código."
    ),
    RUIDO_ADMINISTRATIVO: (
        "Confirmar: el relato es, en sustancia, trámite institucional y no narra un hecho "
        "investigativo propio (solicitudes de información a otra entidad, cartas de remisión, "
        "oficios de traslado de competencia, acuses de recibo). Caso límite: si el oficio narra "
        "además el hecho investigado (no solo pide información), confirma el fenómeno que "
        "corresponda, no ruido administrativo solo."
    ),
    NO_CLASIFICADO: (
        "Resultado legítimo: ninguno de los fenómenos de la taxonomía aplica con claridad a "
        "este relato ni es ruido administrativo. No fuerces un código solo porque parezca "
        "cercano."
    ),
}


def descripcion_codigo(codigo: str) -> str:
    return DESCRIPCION_CODIGO.get(codigo, "Sin descripción registrada para este código.")


RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CALIFICACIONES_DEFECTO = (
    RAIZ_PROYECTO / "data" / "private" / "anotacion_fenomenos" / "calificaciones.csv"
)
RUTA_RESUMEN_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "i4" / "anotacion_fenomenos.md"
RUTA_TAXONOMIA_DEFECTO = RAIZ_PROYECTO / "config" / "taxonomia" / "v1.0.yaml"

SEPARADOR_CODIGOS = ";"

CAMPOS_CSV = [
    "registro_uid",
    "codigos_sugeridos",
    "decision",
    "codigos_corregidos",
    "calificador",
    "notas",
]


@dataclass(frozen=True)
class CandidatoRelato:
    registro_uid: str
    codigos_sugeridos: tuple[str, ...]


def cargar_codigos_fenomeno(ruta_taxonomia: Path = RUTA_TAXONOMIA_DEFECTO) -> list[str]:
    """Códigos aprobados de la taxonomía congelada más las dos clases de anotación que no son
    fenómenos de la taxonomía (ruido administrativo, no clasificado) — ver ADR 0024."""
    contenido = yaml.safe_load(ruta_taxonomia.read_text(encoding="utf-8"))
    codigos_taxonomia = [f["codigo"] for f in contenido.get("fenomenos", [])]
    return codigos_taxonomia + list(CODIGOS_ANOTACION_EXTRA)


def _clave_estrato(codigos_sugeridos: tuple[str, ...]) -> str:
    if not codigos_sugeridos:
        return "sin_sugerencia"
    return SEPARADOR_CODIGOS.join(sorted(codigos_sugeridos))


def muestrear_relatos_estratificado(
    candidatos: list[CandidatoRelato], n_total: int, semilla: int = 20260101
) -> list[str]:
    """Reparte `n_total` entre los estratos presentes (combinación de códigos sugeridos por el
    borrador de clustering), lo más parejo posible. A diferencia de
    `muestrear_menciones_estratificado_activo`, no prioriza por confianza: la membresía de
    clustering trae probabilidad fija en 1.0 (`asignacion.py`), no hay señal de incertidumbre que
    priorizar todavía — es muestreo estratificado simple, no aprendizaje activo.
    """
    por_estrato: dict[str, list[CandidatoRelato]] = defaultdict(list)
    for candidato in candidatos:
        por_estrato[_clave_estrato(candidato.codigos_sugeridos)].append(candidato)

    estratos = sorted(por_estrato)
    if not estratos:
        return []

    rng = random.Random(semilla)
    cupo_por_estrato = max(1, n_total // len(estratos))

    seleccionados: list[str] = []
    for estrato in estratos:
        grupo = por_estrato[estrato]
        rng.shuffle(grupo)
        seleccionados.extend(c.registro_uid for c in grupo[:cupo_por_estrato])
    return seleccionados[:n_total]


def _serializar_codigos(codigos: list[str] | tuple[str, ...]) -> str:
    return SEPARADOR_CODIGOS.join(sorted(codigos))


def _deserializar_codigos(texto: str) -> list[str]:
    return [c for c in texto.split(SEPARADOR_CODIGOS) if c]


def guardar_calificacion_fenomeno(
    ruta_csv: Path,
    registro_uid: str,
    codigos_sugeridos: list[str],
    decision: str,
    calificador: str,
    codigos_corregidos: list[str] | None = None,
    notas: str | None = None,
) -> None:
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    escribir_encabezado = not ruta_csv.exists()
    with ruta_csv.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_CSV)
        if escribir_encabezado:
            escritor.writeheader()
        escritor.writerow(
            {
                "registro_uid": registro_uid,
                "codigos_sugeridos": _serializar_codigos(codigos_sugeridos),
                "decision": decision,
                "codigos_corregidos": _serializar_codigos(codigos_corregidos or []),
                "calificador": calificador,
                "notas": notas or "",
            }
        )


def cargar_calificaciones_fenomeno(ruta_csv: Path) -> list[dict[str, str]]:
    if not ruta_csv.exists():
        return []
    with ruta_csv.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def codigos_efectivos(fila: dict[str, str]) -> list[str]:
    """El conjunto de códigos que vale para entrenamiento/cobertura: los corregidos si hubo
    corrección (incluso vacíos → no_clasificado), si no los sugeridos que el analista confirmó."""
    if fila["decision"] == CORREGIDA:
        return _deserializar_codigos(fila["codigos_corregidos"]) or [NO_CLASIFICADO]
    return _deserializar_codigos(fila["codigos_sugeridos"]) or [NO_CLASIFICADO]


def calcular_cobertura_por_codigo(
    calificaciones: list[dict[str, str]], codigos: list[str]
) -> dict[str, int]:
    conteos = dict.fromkeys(codigos, 0)
    for fila in calificaciones:
        for codigo in codigos_efectivos(fila):
            if codigo in conteos:
                conteos[codigo] += 1
    return conteos


def agrupar_calificaciones_por_calificador(
    calificaciones: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Agrupa las filas por quién calificó (`calificador`), para que quien llama pueda elegir un
    par de anotadores y calcular kappa de Cohen sobre los `registro_uid` que ambos calificaron."""
    agrupadas: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fila in calificaciones:
        agrupadas[fila["calificador"]].append(fila)
    return dict(agrupadas)


def calcular_kappa_por_codigo(
    calificaciones_a: list[dict[str, str]],
    calificaciones_b: list[dict[str, str]],
    codigos: list[str],
) -> dict[str, float | None]:
    """Kappa de Cohen por código (no global, igual criterio que `herramienta_anotacion_menciones`
    / `guia_anotacion_fenomenos.md`), calculado solo sobre los `registro_uid` que ambos
    anotadores calificaron.
    """
    por_uid_a = {fila["registro_uid"]: codigos_efectivos(fila) for fila in calificaciones_a}
    por_uid_b = {fila["registro_uid"]: codigos_efectivos(fila) for fila in calificaciones_b}
    uids_comunes = sorted(set(por_uid_a) & set(por_uid_b))

    resultado: dict[str, float | None] = {}
    for codigo in codigos:
        if len(uids_comunes) < 2:
            resultado[codigo] = None
            continue
        etiquetas_a = [1 if codigo in por_uid_a[uid] else 0 for uid in uids_comunes]
        etiquetas_b = [1 if codigo in por_uid_b[uid] else 0 for uid in uids_comunes]
        if len(set(etiquetas_a)) < 2 and len(set(etiquetas_b)) < 2:
            resultado[codigo] = None
            continue
        resultado[codigo] = round(float(cohen_kappa_score(etiquetas_a, etiquetas_b)), 4)
    return resultado


def escribir_resumen(
    cobertura: dict[str, int],
    minimo_por_codigo: int,
    kappa_por_codigo: dict[str, float | None] | None = None,
    n_relatos_doble_anotados: int | None = None,
    n_relatos_totales: int | None = None,
    ruta_salida: Path = RUTA_RESUMEN_DEFECTO,
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Anotación de fenómenos por relato — cobertura y acuerdo (ADR 0024)",
        "",
        f"Mínimo exigido por código antes de entrenar (CLAUDE.md §2.3): {minimo_por_codigo}.",
        "",
        "| código | confirmados/corregidos | alcanza el mínimo | kappa de Cohen |",
        "|---|---|---|---|",
    ]
    for codigo, n in sorted(cobertura.items()):
        alcanza = "sí" if n >= minimo_por_codigo else "no"
        kappa = (kappa_por_codigo or {}).get(codigo)
        lineas.append(f"| {codigo} | {n} | {alcanza} | {kappa if kappa is not None else '—'} |")
    lineas.append("")
    if n_relatos_totales:
        n_doble = n_relatos_doble_anotados or 0
        porcentaje = round(100 * n_doble / n_relatos_totales, 1)
        alcanza_doble = "sí" if porcentaje >= 20 else "no"
        lineas.append(
            f"Relatos con doble anotación: {n_doble}/{n_relatos_totales} ({porcentaje} %) — "
            f"mínimo pedido por el piloto (ADR 0024): 20 % ({alcanza_doble})."
        )
        lineas.append("")
    lineas.append(
        "Mientras algún código no alcance el mínimo, `make entrenar-clasificador-fenomenos` "
        "rechaza entrenar (`decla.fenomenos.clasificador.verificar_cobertura_minima`)."
    )
    ruta_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class CandidatoFenomenoNuevo:
    codigo_propuesto: str
    n_propuesto: int


def identificar_candidatos_fenomeno_nuevo(
    calificaciones: list[dict[str, str]], codigos_conocidos: set[str]
) -> list[CandidatoFenomenoNuevo]:
    """Términos que un analista escribió en el campo libre "otro, especifica" al corregir un
    relato, y que NO están entre `codigos_conocidos` (los de `cargar_codigos_fenomeno`). Mismo
    patrón que `herramienta_anotacion_menciones.identificar_candidatos_mecanismo_nuevo` (ADR
    0020): nunca se descarta la señal ni se agrega sola a la taxonomía — se cuenta para que un
    analista decida si la formaliza en un taller de revisión (CLAUDE.md §2.3, plan §7.2).
    """
    conteos: dict[str, int] = defaultdict(int)
    for fila in calificaciones:
        if fila.get("decision") != CORREGIDA:
            continue
        for codigo in _deserializar_codigos(fila.get("codigos_corregidos", "")):
            if codigo not in codigos_conocidos:
                conteos[codigo] += 1

    return sorted(
        (CandidatoFenomenoNuevo(codigo, n) for codigo, n in conteos.items()),
        key=lambda c: (-c.n_propuesto, c.codigo_propuesto),
    )


RUTA_CANDIDATOS_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "i4" / "candidatos_fenomeno_nuevo.csv"
)


def escribir_candidatos_fenomeno_nuevo(
    candidatos: list[CandidatoFenomenoNuevo], ruta_salida: Path = RUTA_CANDIDATOS_DEFECTO
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["codigo_propuesto", "n_propuesto"])
        for candidato in candidatos:
            escritor.writerow([candidato.codigo_propuesto, candidato.n_propuesto])


def construir_candidatos_desde_borrador(
    filas_asignacion: list[dict[str, Any]],
) -> list[CandidatoRelato]:
    """A partir de filas de `fenomenos.asignacion_fenomeno` (registro_uid, codigo_fenomeno) más
    los relatos sin ninguna fila (candidatos implícitos a `no_clasificado`), agrupa por
    `registro_uid` los códigos sugeridos. Quien llama decide cómo obtener el universo completo
    de `registro_uid` (p. ej. `texto.relato_procesado`) para incluir también los sin asignación.
    """
    por_registro: dict[str, list[str]] = defaultdict(list)
    for fila in filas_asignacion:
        por_registro[fila["registro_uid"]].append(fila["codigo_fenomeno"])
    return [
        CandidatoRelato(registro_uid=uid, codigos_sugeridos=tuple(sorted(set(codigos))))
        for uid, codigos in por_registro.items()
    ]
