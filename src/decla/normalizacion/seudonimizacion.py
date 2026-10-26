"""Seudonimización HMAC-SHA256 de `NUMERO_DOCUMENTO` y `FISCAL_ASIGNADO_DESPACHO` (CLAUDE.md
§2.1, §3.3).

La clave vive en `data/private/claves/`, fuera de git y bloqueada para las herramientas de
Claude Code. `obtener_o_crear_clave` solo corre cuando la persona ejecuta `make etl` en su
máquina: Claude Code nunca crea ni lee ese archivo.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

LONGITUD_CLAVE_BYTES = 32


def obtener_o_crear_clave(ruta_clave: Path) -> bytes:
    if ruta_clave.exists():
        return ruta_clave.read_bytes()
    ruta_clave.parent.mkdir(parents=True, exist_ok=True)
    clave = secrets.token_bytes(LONGITUD_CLAVE_BYTES)
    ruta_clave.write_bytes(clave)
    os.chmod(ruta_clave, 0o600)
    return clave


def seudonimizar(valor: str | None, clave: bytes) -> str | None:
    if valor is None:
        return None
    return hmac.new(clave, valor.encode("utf-8"), hashlib.sha256).hexdigest()
