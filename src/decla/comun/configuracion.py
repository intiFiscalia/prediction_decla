"""Carga de configuración declarativa en YAML (CLAUDE.md §3.4: "configuración en YAML, no
constantes ocultas en el código").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def cargar_yaml(ruta: Path) -> dict[str, Any]:
    with ruta.open("r", encoding="utf-8") as archivo:
        contenido = yaml.safe_load(archivo)
    return contenido or {}
