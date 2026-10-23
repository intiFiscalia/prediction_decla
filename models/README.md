# models/

Modelos preentrenados descargados una sola vez con `scripts/descargar_modelos.py` a partir de
`config/modelos.yaml`, cargados siempre desde ruta local (`HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`). Cada modelo se registra en `MANIFEST.json` con nombre, versión, licencia,
hash SHA-256 y fecha; el código verifica el hash antes de cargar cualquier modelo.

Los pesos de los modelos no se versionan en git (ver `.gitignore`); solo `MANIFEST.json` se comparte.

Lectura: cualquier colaborador del proyecto, incluido Claude Code (solo metadatos, nunca pesos binarios
grandes en el repo).
