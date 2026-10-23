"""Entorno de ejecución 100% local (CLAUDE.md §2.2).

Fija variables de entorno que impiden descargas o telemetría en tiempo de ejecución y verifica
que cada modelo cargado desde `models/` coincida con el hash registrado en su MANIFEST.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
MANIFEST_MODELOS = RAIZ_PROYECTO / "models" / "MANIFEST.json"


class ModeloNoVerificadoError(RuntimeError):
    """El hash de un modelo local no coincide con el registrado en MANIFEST.json."""


@dataclass(frozen=True)
class EntradaManifiesto:
    nombre: str
    tipo: str
    ruta_local: str
    hash_sha256: str
    licencia: str
    fecha: str
    version: str | None = None


def configurar_entorno_offline() -> None:
    """Desactiva descargas y telemetría de las librerías que las tienen."""
    for variable, valor in (
        ("HF_HUB_OFFLINE", "1"),
        ("TRANSFORMERS_OFFLINE", "1"),
        ("DO_NOT_TRACK", "1"),
        ("TOKENIZERS_PARALLELISM", "false"),
    ):
        os.environ.setdefault(variable, valor)


def hash_directorio(ruta: Path) -> str:
    """Hash estable de todos los archivos de un directorio (orden determinista por ruta)."""
    digest = hashlib.sha256()
    archivos = sorted(p for p in ruta.rglob("*") if p.is_file())
    for archivo in archivos:
        digest.update(archivo.relative_to(ruta).as_posix().encode("utf-8"))
        digest.update(archivo.read_bytes())
    return digest.hexdigest()


def hash_archivo(ruta: Path) -> str:
    digest = hashlib.sha256()
    digest.update(ruta.read_bytes())
    return digest.hexdigest()


def cargar_manifiesto(ruta_manifiesto: Path = MANIFEST_MODELOS) -> dict[str, EntradaManifiesto]:
    if not ruta_manifiesto.exists():
        return {}
    datos = json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
    return {
        entrada["nombre"]: EntradaManifiesto(
            nombre=entrada["nombre"],
            tipo=entrada["tipo"],
            ruta_local=entrada["ruta_local"],
            hash_sha256=entrada["hash_sha256"],
            licencia=entrada["licencia"],
            fecha=entrada["fecha"],
            version=entrada.get("version"),
        )
        for entrada in datos.get("modelos", [])
    }


def verificar_hash_modelo(
    nombre: str, raiz_proyecto: Path = RAIZ_PROYECTO, ruta_manifiesto: Path = MANIFEST_MODELOS
) -> EntradaManifiesto:
    """Recalcula el hash del modelo `nombre` y lo compara contra el MANIFEST.

    Lanza `ModeloNoVerificadoError` si el modelo no está en el manifiesto, si la ruta local no
    existe, o si el hash recalculado no coincide (archivo corrupto, modificado o sustituido).
    """
    manifiesto = cargar_manifiesto(ruta_manifiesto)
    if nombre not in manifiesto:
        raise ModeloNoVerificadoError(f"'{nombre}' no está registrado en {ruta_manifiesto}")

    entrada = manifiesto[nombre]
    ruta_local = raiz_proyecto / entrada.ruta_local
    if not ruta_local.exists():
        raise ModeloNoVerificadoError(f"'{nombre}' no existe en {ruta_local}")

    hash_actual = hash_directorio(ruta_local) if ruta_local.is_dir() else hash_archivo(ruta_local)
    if hash_actual != entrada.hash_sha256:
        raise ModeloNoVerificadoError(
            f"Hash de '{nombre}' no coincide con MANIFEST.json "
            f"(esperado {entrada.hash_sha256[:12]}…, obtenido {hash_actual[:12]}…)"
        )
    return entrada
