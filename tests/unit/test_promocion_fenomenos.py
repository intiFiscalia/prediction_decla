from decla.fenomenos.promocion import construir_filas_promocion


def test_construir_filas_promocion_excluye_codigos_fuera_de_taxonomia() -> None:
    filas_modelo = [
        {
            "registro_uid": "r1",
            "codigo_fenomeno": "organizacion_criminal",
            "confianza": 0.7,
            "version_modelo": "v1-abc",
            "run_id": "run1",
        },
        {
            "registro_uid": "r2",
            "codigo_fenomeno": "ruido_administrativo",
            "confianza": 0.9,
            "version_modelo": "v1-abc",
            "run_id": "run1",
        },
        {
            "registro_uid": "r3",
            "codigo_fenomeno": "no_clasificado",
            "confianza": 0.5,
            "version_modelo": "v1-abc",
            "run_id": "run1",
        },
    ]
    filas = construir_filas_promocion(filas_modelo, ["organizacion_criminal"], "1.0")
    assert len(filas) == 1
    assert filas[0]["registro_uid"] == "r1"
    assert filas[0]["codigo_fenomeno"] == "organizacion_criminal"
    assert filas[0]["metodo_origen"] == "clasificador_fenomenos:v1-abc"
    assert filas[0]["probabilidad"] == 0.7
    assert filas[0]["version_taxonomia"] == "1.0"
    assert filas[0]["run_id"] == "run1"


def test_construir_filas_promocion_sin_filas_devuelve_vacio() -> None:
    assert construir_filas_promocion([], ["organizacion_criminal"], "1.0") == []
