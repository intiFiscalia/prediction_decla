"""Logger JSON estructurado que nunca emite contenido de filas (CLAUDE.md §2.1, §3.4).

El logger no escanea texto libre buscando datos sensibles (no es confiable). En vez de eso expone
una API de **lista blanca**: `registrar_evento` solo acepta los campos declarados en
`CAMPOS_PERMITIDOS` (conteos, nombres de columna, tipos, ids, versiones). Cualquier otro campo
—incluidos los que sugieren contenido de fila, como `fila`, `valor`, `relato`, `nombre`,
`documento`— se rechaza con un error antes de llegar al logger.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

CAMPOS_PERMITIDOS: frozenset[str] = frozenset(
    {
        "run_id",
        "lote_id",
        "registro_uid",
        "version_taxonomia",
        "version_modelo",
        "version_extractor",
        "conteo",
        "conteos",
        "n",
        "n_entrada",
        "n_salida",
        "n_cuarentena",
        "columna",
        "columnas",
        "tipo",
        "tipos",
        "total",
        "duracion_s",
        "estado",
        "version",
        "codigo_error",
        "ruta",
        "extractor",
        "modelo",
        "paso",
        "commit_git",
    }
)


class CampoNoPermitidoError(ValueError):
    """Se intentó registrar un campo fuera de la lista blanca de `registro.py`."""


def configurar_logging(nivel: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(nivel),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def obtener_logger(nombre: str) -> Any:
    return structlog.get_logger(nombre)


def registrar_evento(logger: Any, mensaje: str, **campos: Any) -> None:
    """Registra un evento solo con campos de `CAMPOS_PERMITIDOS`.

    Lanza `CampoNoPermitidoError` si algún campo no está en la lista blanca, en vez de intentar
    adivinar si el valor contiene datos sensibles.
    """
    desconocidos = set(campos) - CAMPOS_PERMITIDOS
    if desconocidos:
        raise CampoNoPermitidoError(
            f"Campos no permitidos en log: {sorted(desconocidos)}. "
            "Los logs solo admiten conteos, columnas, tipos e ids (CLAUDE.md §2.1, §3.4); "
            "nunca contenido de filas."
        )
    logger.info(mensaje, **campos)
