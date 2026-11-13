"""Clasificación zero-shot de mecanismos/actividades por similitud de embeddings contra
definiciones semilla (plan_trabajo.md §6.2, fila "Actividades y mecanismos explícitos": lo que el
diccionario no cubre se clasifica "por similitud con definiciones semilla"). Mismo patrón que
`decla.conocimiento.sectores` (CIIU inferido): nunca fuerza una etiqueta si la confianza o el
margen no superan los umbrales de `config/umbrales.yaml`; por debajo del umbral queda
`"no_clasificado"`, un resultado legítimo (plan_trabajo.md §7.3), no un error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from decla.comun.configuracion import cargar_yaml
from decla.texto.embeddings import (
    MEDIA,
    FragmentoEmbedding,
    calcular_embeddings_relato,
    calcular_vectores_oraciones,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CATEGORIAS = RAIZ_PROYECTO / "config" / "categorias_menciones.yaml"
RUTA_EXPRESIONES_MECANISMO = (
    RAIZ_PROYECTO / "config" / "diccionarios" / "mecanismos_expresiones.yaml"
)

ORIGEN_EXPLICITO = "explicito_regla"
ORIGEN_INFERIDO = "inferido_modelo"
NO_CLASIFICADO = "no_clasificado"


@dataclass(frozen=True)
class DefinicionSemilla:
    codigo: str
    definicion: str


@dataclass(frozen=True)
class ClasificacionZeroShot:
    codigo: str | None
    confianza: float
    origen: str
    texto_evidencia: str | None = None


@dataclass(frozen=True)
class ClasificacionMecanismoExplicito:
    codigo: str
    texto_evidencia: str


def cargar_expresiones_mecanismo(
    ruta: Path = RUTA_EXPRESIONES_MECANISMO,
) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    return list(cargar_yaml(ruta).get("expresiones", []))


def clasificar_mecanismo_explicito(
    texto: str, expresiones: list[dict[str, str]]
) -> ClasificacionMecanismoExplicito | None:
    """Coincidencia literal contra `config/diccionarios/mecanismos_expresiones.yaml`, intentada
    **antes** del modelo zero-shot (`clasificar_fragmento`). Devuelve `None` si ninguna expresión
    aparece — nunca fuerza un código, y el texto sigue cayendo al modelo. Este nivel nunca
    reemplaza al modelo como vía de descubrimiento: solo acelera y hace exacto lo que el
    diccionario ya anticipa; cualquier mecanismo nuevo no listado aquí sigue dependiendo del
    modelo para aparecer (aunque sea como candidato de baja confianza a revisar).
    """
    for entrada in expresiones:
        patron = re.compile(re.escape(entrada["expresion"]), re.IGNORECASE)
        coincidencia = patron.search(texto)
        if coincidencia is None:
            continue
        return ClasificacionMecanismoExplicito(
            codigo=entrada["code"], texto_evidencia=coincidencia.group()
        )
    return None


def cargar_vocabulario(
    nombre_categoria: str, ruta: Path = RUTA_CATEGORIAS
) -> list[DefinicionSemilla]:
    contenido = cargar_yaml(ruta)
    for categoria in contenido["categorias"]:
        if categoria["nombre"] == nombre_categoria:
            return [
                DefinicionSemilla(entrada["codigo"], entrada["definicion"])
                for entrada in categoria.get("vocabulario", [])
                if "definicion" in entrada
            ]
    return []


def calcular_vectores_vocabulario(
    definiciones: list[DefinicionSemilla], nombre_modelo: str
) -> dict[str, list[float]]:
    vectores = {}
    for definicion in definiciones:
        embeddings = calcular_embeddings_relato(
            definicion.codigo, definicion.definicion, nombre_modelo
        )
        vector = next((e.vector for e in embeddings if e.agregacion == MEDIA), None)
        if vector is not None:
            vectores[definicion.codigo] = vector
    return vectores


def _similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    norma_a, norma_b = np.linalg.norm(a), np.linalg.norm(b)
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norma_a * norma_b))


def elegir_por_similitud(
    vector_fragmento: list[float],
    vectores_vocabulario: dict[str, list[float]],
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionZeroShot:
    """Parte pura: separada de `clasificar_fragmento` para probar el umbral con vectores
    sintéticos, sin pagar el costo de cargar un modelo de embeddings.
    """
    if len(vectores_vocabulario) < 2:
        return ClasificacionZeroShot(None, 0.0, ORIGEN_INFERIDO)

    arreglo = np.array(vector_fragmento)
    similitudes = sorted(
        (
            (codigo, _similitud_coseno(arreglo, np.array(vector)))
            for codigo, vector in vectores_vocabulario.items()
        ),
        key=lambda par: -par[1],
    )
    (codigo_top1, sim_top1), (_, sim_top2) = similitudes[0], similitudes[1]
    margen = sim_top1 - sim_top2

    if sim_top1 < confianza_minima or margen < margen_minimo_top2:
        return ClasificacionZeroShot(NO_CLASIFICADO, round(sim_top1, 4), ORIGEN_INFERIDO)
    return ClasificacionZeroShot(codigo_top1, round(sim_top1, 4), ORIGEN_INFERIDO)


def elegir_mejor_fragmento(
    fragmentos: list[FragmentoEmbedding],
    vectores_vocabulario: dict[str, list[float]],
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionZeroShot:
    """Aplica `elegir_por_similitud` a cada fragmento (una oración,
    `decla.texto.embeddings.calcular_vectores_oraciones`) y devuelve el de mayor confianza, con
    el texto de la oración ganadora como evidencia. Comparar el relato completo (agregación
    MEDIA) contra una definición de una sola oración diluye una mención puntual de un mecanismo
    entre el resto del texto genérico; comparar oración por oración deja que una sola oración
    relevante gane aunque el resto del relato no se le parezca.
    """
    if not fragmentos or len(vectores_vocabulario) < 2:
        return ClasificacionZeroShot(None, 0.0, ORIGEN_INFERIDO)

    mejor: ClasificacionZeroShot | None = None
    mejor_texto = ""
    for fragmento in fragmentos:
        resultado = elegir_por_similitud(
            fragmento.vector, vectores_vocabulario, confianza_minima, margen_minimo_top2
        )
        if mejor is None or resultado.confianza > mejor.confianza:
            mejor = resultado
            mejor_texto = fragmento.texto

    assert mejor is not None
    return ClasificacionZeroShot(mejor.codigo, mejor.confianza, mejor.origen, mejor_texto)


def clasificar_fragmento(
    fragmento: str,
    vectores_vocabulario: dict[str, list[float]],
    nombre_modelo: str,
    confianza_minima: float,
    margen_minimo_top2: float,
) -> ClasificacionZeroShot:
    if not fragmento or not fragmento.strip():
        return ClasificacionZeroShot(None, 0.0, ORIGEN_INFERIDO)

    fragmentos = calcular_vectores_oraciones(fragmento, nombre_modelo)
    return elegir_mejor_fragmento(
        fragmentos, vectores_vocabulario, confianza_minima, margen_minimo_top2
    )
