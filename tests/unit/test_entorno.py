import json
from pathlib import Path

import pytest

from decla.comun.entorno import ModeloNoVerificadoError, hash_directorio, verificar_hash_modelo


def _preparar_manifiesto(tmp_path: Path) -> Path:
    modelo_dir = tmp_path / "models" / "modelo_prueba"
    modelo_dir.mkdir(parents=True)
    (modelo_dir / "pesos.bin").write_bytes(b"contenido-sintetico-de-prueba")

    manifest_path = tmp_path / "models" / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "modelos": [
                    {
                        "nombre": "modelo_prueba",
                        "tipo": "sentence-transformers",
                        "ruta_local": "models/modelo_prueba",
                        "hash_sha256": hash_directorio(modelo_dir),
                        "licencia": "MIT",
                        "fecha": "2026-01-01",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_verificar_hash_modelo_ok(tmp_path: Path) -> None:
    manifest_path = _preparar_manifiesto(tmp_path)
    entrada = verificar_hash_modelo(
        "modelo_prueba", raiz_proyecto=tmp_path, ruta_manifiesto=manifest_path
    )
    assert entrada.nombre == "modelo_prueba"


def test_verificar_hash_modelo_falla_si_se_manipula(tmp_path: Path) -> None:
    manifest_path = _preparar_manifiesto(tmp_path)
    (tmp_path / "models" / "modelo_prueba" / "pesos.bin").write_bytes(b"contenido-modificado")

    with pytest.raises(ModeloNoVerificadoError):
        verificar_hash_modelo(
            "modelo_prueba", raiz_proyecto=tmp_path, ruta_manifiesto=manifest_path
        )


def test_verificar_hash_modelo_falla_si_no_existe(tmp_path: Path) -> None:
    manifest_path = tmp_path / "models" / "MANIFEST.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"modelos": []}), encoding="utf-8")

    with pytest.raises(ModeloNoVerificadoError):
        verificar_hash_modelo(
            "inexistente", raiz_proyecto=tmp_path, ruta_manifiesto=manifest_path
        )
