"""Descarga a `models/` los modelos preentrenados de `config/modelos.yaml`.

Se ejecuta UNA VEZ en una máquina autorizada con acceso a internet (CLAUDE.md §2.2). De ahí en
adelante, todo el proyecto carga los modelos desde ruta local en modo offline
(`decla.comun.entorno.configurar_entorno_offline`) y verifica su hash contra `models/MANIFEST.json`
antes de usarlos.

Uso:
    uv run python scripts/descargar_modelos.py --dry-run
    uv run python scripts/descargar_modelos.py --solo paraphrase-multilingual-mpnet-base-v2
    uv run python scripts/descargar_modelos.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date
from datetime import datetime as dt
from pathlib import Path

import yaml

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
CONFIG_MODELOS = RAIZ_PROYECTO / "config" / "modelos.yaml"
DESTINO_MODELOS = RAIZ_PROYECTO / "models"
MANIFEST = DESTINO_MODELOS / "MANIFEST.json"


def cargar_catalogo(ruta: Path = CONFIG_MODELOS) -> list[dict]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return datos["modelos"]


def _hash_directorio(ruta: Path) -> str:
    from decla.comun.entorno import hash_directorio

    return hash_directorio(ruta)


def _descargar_sentence_transformer(repo_id: str, destino: Path) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=repo_id, local_dir=str(destino))


def _descargar_spacy_wheel(url: str, destino: Path) -> None:
    import urllib.request

    destino.mkdir(parents=True, exist_ok=True)
    nombre_archivo = url.rsplit("/", 1)[-1]
    urllib.request.urlretrieve(url, destino / nombre_archivo)  # noqa: S310 (fuente fija y conocida)


def descargar_modelo(entrada: dict, destino_base: Path = DESTINO_MODELOS) -> Path:
    destino = destino_base / entrada["id"]
    if entrada["tipo"] == "sentence-transformers":
        _descargar_sentence_transformer(entrada["repo_id"], destino)
    elif entrada["tipo"] == "spacy":
        _descargar_spacy_wheel(entrada["origen"], destino)
    else:
        raise ValueError(f"Tipo de modelo no soportado: {entrada['tipo']}")
    return destino


def actualizar_manifiesto(
    entrada: dict, ruta_local: Path, manifest_path: Path = MANIFEST
) -> None:
    manifiesto = {"modelos": []}
    if manifest_path.exists():
        manifiesto = json.loads(manifest_path.read_text(encoding="utf-8"))

    hash_modelo = _hash_directorio(ruta_local)
    nueva_entrada = {
        "nombre": entrada["id"],
        "tipo": entrada["tipo"],
        "origen": entrada.get("repo_id") or entrada.get("origen"),
        "ruta_local": str(ruta_local.relative_to(RAIZ_PROYECTO)),
        "licencia": entrada["licencia"],
        "hash_sha256": hash_modelo,
        "fecha": date.today().isoformat(),
        "descargado_en_utc": dt.now(UTC).isoformat(),
    }
    manifiesto["modelos"] = [
        m for m in manifiesto["modelos"] if m["nombre"] != entrada["id"]
    ] + [nueva_entrada]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Lista qué se descargaría, sin red.")
    parser.add_argument("--solo", help="Descarga solo el modelo con este id.")
    args = parser.parse_args(argv)

    catalogo = cargar_catalogo()
    if args.solo:
        catalogo = [m for m in catalogo if m["id"] == args.solo]
        if not catalogo:
            print(f"No existe el modelo '{args.solo}' en {CONFIG_MODELOS}", file=sys.stderr)
            return 1

    for entrada in catalogo:
        destino = DESTINO_MODELOS / entrada["id"]
        if args.dry_run:
            print(f"[dry-run] descargaría '{entrada['id']}' ({entrada['tipo']}) -> {destino}")
            continue
        print(f"Descargando '{entrada['id']}'...")
        ruta_local = descargar_modelo(entrada)
        actualizar_manifiesto(entrada, ruta_local)
        print(f"  listo: {ruta_local}, registrado en {MANIFEST}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
