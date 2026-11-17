#!/usr/bin/env bash
# Descarga a wheelhouse/ todas las ruedas necesarias para instalar el proyecto sin internet.
# Se ejecuta UNA VEZ en una máquina autorizada con acceso a internet (CLAUDE.md §2.2).
# `make instalar` en la máquina de producción instala solo desde wheelhouse/ con --no-index.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELHOUSE="${RAIZ}/wheelhouse"

mkdir -p "${WHEELHOUSE}"

echo "Descargando ruedas de todos los extras a ${WHEELHOUSE}..."
cd "${RAIZ}"
uv pip compile pyproject.toml --extra base --extra nlp --extra fenomenos --extra fenomenos_llm \
  --extra analitica --extra app --extra dev -o "${WHEELHOUSE}/requisitos.txt"
uv pip download -r "${WHEELHOUSE}/requisitos.txt" -d "${WHEELHOUSE}"

echo "Listo. Copia ${WHEELHOUSE}/ al medio físico/espejo interno autorizado para la máquina de producción."
