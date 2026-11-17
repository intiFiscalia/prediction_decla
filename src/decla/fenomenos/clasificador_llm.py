"""Clasificación de fenómenos por relato con un LLM generativo local (ADR 0027, reemplaza la
cascada de ADR 0026).

El LLM clasifica el 100% de los relatos — no hay clasificador rápido filtrando qué revisa (ADR
0027: la persona decidió priorizar rigor sobre velocidad; el costo de tiempo se paga en lotes
batch, nunca online). Las funciones de construcción de prompt y parseo son puras y se prueban con
un `ClienteLLM` falso, sin descargar pesos reales en CI; `ClienteMLX` es el único punto que
importa `mlx`/`mlx-lm` (extra opcional `fenomenos_llm`), con import perezoso para que el resto
del módulo no dependa de tenerlo instalado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from unidecode import unidecode

from decla.fenomenos.herramienta_anotacion_fenomeno import descripcion_codigo

TEMPERATURA_DEFECTO = 0.0
SEMILLA_DEFECTO = 20260101
MAX_TOKENS_RESPUESTA = 400


class ClienteLLM(Protocol):
    def generar(self, prompt: str, temperatura: float, semilla: int) -> str: ...


@dataclass(frozen=True)
class ResultadoClasificacionLLM:
    codigos: list[str]
    evidencia: str
    confianza: float
    organizacion_mencionada: str | None = None
    fenomeno_no_listado: str | None = None


def construir_prompt(relato_enmascarado: str, codigos_disponibles: list[str]) -> str:
    """El criterio de confirmación/caso límite por código es el mismo que usa el analista humano
    en `docs/fichas/guia_anotacion_fenomenos.md` (vía `descripcion_codigo`) — nunca un criterio
    distinto inventado para el LLM. `organizacion_mencionada` es un campo abierto (no hay
    taxonomía cerrada de organizaciones criminales, ADR 0028): solo el nombre tal como el relato
    lo menciona explícitamente, nunca una inferencia ("parece ser de tal grupo"). Igual con
    `fenomeno_no_listado` (ADR 0029): si el relato describe algo relevante que no encaja en
    ninguno de los 3 códigos, se describe como candidato en vez de forzarlo en el código más
    parecido — mismo patrón que "otro, especifica" de la anotación humana (ADR 0020/0024)."""
    criterios = "\n".join(
        f"- {codigo}: {descripcion_codigo(codigo)}" for codigo in codigos_disponibles
    )
    return (
        "Eres un analista que clasifica relatos de casos judiciales de lavado de activos. "
        "El relato ya está enmascarado (sin datos personales). Decide cuáles de los siguientes "
        "códigos aplican, siguiendo EXACTAMENTE estos criterios de confirmación y casos límite:\n"
        f"{criterios}\n\n"
        "Un relato puede tener varios códigos, uno solo, o ninguno (si ninguno aplica con "
        "claridad, responde \"codigos\": []). No multipliques códigos por generosidad: cada "
        "código necesita evidencia textual directa del relato, no una inferencia encadenada "
        "desde otro código. NUNCA fuerces un código que no encaja solo porque es el 'más "
        "parecido' (p. ej. hallazgo de esmeraldas u otro bien de alto valor sin documentación NO "
        "es 'incautacion_y_conteo_de_efectivo', que es específicamente dinero en efectivo) — en "
        "ese caso usa 'fenomeno_no_listado' en vez de forzar el código.\n\n"
        "Además, revisa si el relato menciona EXPLÍCITAMENTE el nombre de una organización "
        "criminal o grupo armado como responsable o asociado al hecho (p. ej. \"la organización "
        "detrás de la incautación fue el grupo X\"). Esto es raro: la mayoría de los relatos no "
        "lo menciona. Si lo menciona, copia el nombre tal como aparece en el texto en "
        "'organizacion_mencionada'; si no lo menciona, o solo lo sugiere sin nombrarlo, usa "
        "null — nunca adivines ni infieras un nombre que el relato no dice.\n\n"
        "Si el relato describe con claridad algo relevante para lavado de activos que NO encaja "
        "en ninguno de los 3 códigos de arriba (como el ejemplo de las esmeraldas), describe en "
        "una frase corta qué viste en 'fenomeno_no_listado'; si todo lo relevante ya quedó "
        "cubierto por los códigos existentes, o no hay nada relevante, usa null.\n\n"
        f"RELATO:\n{relato_enmascarado}\n\n"
        "Responde ÚNICAMENTE un objeto JSON con esta forma exacta, sin texto fuera del JSON:\n"
        '{"codigos": ["codigo_1", "..."], "evidencia": "cita breve del relato que lo justifica", '
        '"confianza": 0.0, "organizacion_mencionada": null, "fenomeno_no_listado": null}'
    )


def _quitar_valla_markdown(texto: str) -> str:
    """Algunos LLMs envuelven el JSON en una valla de markdown (```json ... ```) aunque el
    prompt pida responder solo JSON — se quita antes de parsear, nunca se asume que el modelo
    obedeció el formato al pie de la letra (fallo real observado con Qwen2.5-14B)."""
    texto = texto.strip()
    if texto.startswith("```"):
        primera_linea, _, resto = texto.partition("\n")
        texto = resto if primera_linea.strip().lstrip("`").strip() in ("", "json") else texto
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()


def _decodificar_primer_json(texto: str) -> dict[str, Any]:
    """Algunos LLMs agregan texto narrativo después del JSON (razonamiento adicional, un segundo
    intento, etc. — fallo real observado con Qwen2.5-14B) aunque el prompt pida solo JSON; se
    decodifica el primer objeto balanceado y se ignora cualquier texto sobrante, en vez de exigir
    que la respuesta completa sea JSON puro."""
    texto_limpio = _quitar_valla_markdown(texto)
    inicio = texto_limpio.find("{")
    if inicio == -1:
        raise ValueError(f"Respuesta del LLM no es JSON válido: {texto!r}")
    try:
        datos, _ = json.JSONDecoder().raw_decode(texto_limpio, inicio)
    except json.JSONDecodeError as error:
        raise ValueError(f"Respuesta del LLM no es JSON válido: {texto!r}") from error
    if not isinstance(datos, dict):
        raise ValueError(f"Respuesta del LLM no es un objeto JSON: {texto!r}")
    return datos


def _normalizar_codigos(
    codigos_crudos: list[Any], codigos_disponibles: list[str]
) -> tuple[list[str], list[Any]]:
    """Compara ignorando tildes/mayúsculas (`Unidecode`, ya parte del stack aprobado) —
    fallo real observado: el modelo escribió `lavado_de_activos_a_través_de_empresas` (con
    tilde) cuando el código exacto de la taxonomía es sin tilde. Devuelve siempre la forma
    canónica de `codigos_disponibles`, nunca la variante que escribió el modelo, para que lo
    guardado sea idéntico a la taxonomía. Los que no igualan a nada quedan en 'desconocidos'."""
    mapa_normalizado = {unidecode(c).strip().lower(): c for c in codigos_disponibles}
    canonicos: list[str] = []
    desconocidos: list[Any] = []
    for codigo in codigos_crudos:
        clave = unidecode(codigo).strip().lower() if isinstance(codigo, str) else None
        canonico = mapa_normalizado.get(clave) if clave is not None else None
        if canonico is None:
            desconocidos.append(codigo)
        else:
            canonicos.append(canonico)
    return canonicos, desconocidos


def parsear_respuesta_llm(
    texto: str, codigos_disponibles: list[str]
) -> ResultadoClasificacionLLM:
    """Parseo estricto: nunca se confía en texto libre. Si el JSON es inválido, le faltan campos,
    o trae códigos fuera de `codigos_disponibles`, lanza — quien llama decide cómo tratar el
    fallo (reintentar, descartar la fila); nunca se inventa un resultado parcial."""
    datos = _decodificar_primer_json(texto)

    codigos_crudos = datos.get("codigos")
    if not isinstance(codigos_crudos, list):
        raise ValueError(f"La respuesta del LLM no trae una lista 'codigos': {datos!r}")
    codigos, desconocidos = _normalizar_codigos(codigos_crudos, codigos_disponibles)
    if desconocidos:
        raise ValueError(
            f"El LLM devolvió códigos fuera de la taxonomía/anotación: {desconocidos}"
        )

    # Si falta la llave 'confianza' (fallo real observado: el modelo escribió "confida" en vez
    # de "confianza"), no se descarta todo el relato por un nombre de llave mal escrito — se usa
    # el valor más cauteloso (0.0) y se conservan los códigos que sí se parsearon bien. Un valor
    # presente pero inválido o fuera de rango sigue siendo un fallo real, no se tolera igual.
    confianza_bruta = datos.get("confianza")
    if confianza_bruta is None:
        confianza = 0.0
    else:
        try:
            confianza = float(confianza_bruta)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"La respuesta del LLM no trae 'confianza' numérica: {datos!r}"
            ) from error
        if not 0.0 <= confianza <= 1.0:
            raise ValueError(f"Confianza fuera de rango [0,1]: {confianza}")

    organizacion = _texto_opcional(datos, "organizacion_mencionada")
    fenomeno_no_listado = _texto_opcional(datos, "fenomeno_no_listado")

    return ResultadoClasificacionLLM(
        codigos=codigos,
        evidencia=str(datos.get("evidencia", "")),
        confianza=confianza,
        organizacion_mencionada=organizacion,
        fenomeno_no_listado=fenomeno_no_listado,
    )


def _texto_opcional(datos: dict[str, Any], llave: str) -> str | None:
    """Campos de texto abierto opcionales (`organizacion_mencionada`, `fenomeno_no_listado`):
    deben ser texto o null; una cadena vacía/solo espacios cuenta como "no hay nada que
    reportar", igual que null."""
    valor = datos.get(llave)
    if valor is not None and not isinstance(valor, str):
        raise ValueError(f"'{llave}' debe ser texto o null: {datos!r}")
    return valor.strip() or None if isinstance(valor, str) else None


def clasificar_relato(
    cliente: ClienteLLM,
    relato_enmascarado: str,
    codigos_disponibles: list[str],
    temperatura: float = TEMPERATURA_DEFECTO,
    semilla: int = SEMILLA_DEFECTO,
) -> ResultadoClasificacionLLM:
    prompt = construir_prompt(relato_enmascarado, codigos_disponibles)
    texto = cliente.generar(prompt, temperatura=temperatura, semilla=semilla)
    return parsear_respuesta_llm(texto, codigos_disponibles)


class ClienteMLX:
    """Envoltorio delgado sobre `mlx_lm` (ADR 0026): carga el modelo una sola vez y genera texto
    determinista (`temperatura=0.0` + semilla fija, CLAUDE.md §2.4). Import perezoso de
    `mlx`/`mlx_lm` para que el resto de este módulo no requiera el extra `fenomenos_llm`
    instalado solo para probarse con un cliente falso."""

    def __init__(self, ruta_modelo: Path, nombre_modelo: str = "qwen2.5-14b-instruct-4bit") -> None:
        from mlx_lm import load

        from decla.comun.entorno import configurar_entorno_offline, verificar_hash_modelo

        configurar_entorno_offline()
        verificar_hash_modelo(nombre_modelo)
        self._modelo, self._tokenizador = load(str(ruta_modelo))  # type: ignore[misc]

    def generar(self, prompt: str, temperatura: float, semilla: int) -> str:
        import mlx.core as mx
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        mx.random.seed(semilla)
        texto_prompt = self._tokenizador.apply_chat_template(
            [{"role": "user", "content": prompt}], add_generation_prompt=True
        )
        muestreador = make_sampler(temp=temperatura)
        return generate(
            self._modelo,
            self._tokenizador,
            prompt=texto_prompt,
            sampler=muestreador,
            max_tokens=MAX_TOKENS_RESPUESTA,
        )
