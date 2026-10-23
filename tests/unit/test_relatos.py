from pathlib import Path

import polars as pl

from decla.calidad.relatos import (
    contar_patrones_personales,
    detectar_casi_duplicados_entre_noticias,
    detectar_posible_truncamiento,
    enmascarar_basico,
    es_mayuscula_sostenida,
    perfil_longitud,
    tiene_mojibake,
    verificar_reparacion_mojibake,
)

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_perfil_longitud_basico() -> None:
    relatos = ["hola mundo", "una dos tres cuatro", None, ""]
    perfil = perfil_longitud(relatos)
    assert perfil.n_relatos == 4
    assert perfil.n_vacios == 2
    assert perfil.percentiles_palabras[50] > 0


def test_tiene_mojibake_detecta_cirilico() -> None:
    texto_corrupto = "José".encode("cp1252").decode("cp1251")
    assert tiene_mojibake(texto_corrupto)
    assert not tiene_mojibake("José sin corromper")


def test_verificar_reparacion_mojibake_sin_residuo() -> None:
    original = "El señor José Núñez vehículo público"
    corrupto = original.encode("cp1252", errors="replace").decode("cp1251", errors="replace")
    resultado = verificar_reparacion_mojibake(corrupto)
    assert resultado.fallo_reparacion is False
    assert resultado.sin_residuo is True
    assert resultado.reparado == original


def test_mojibake_round_trip_contra_fixture_real() -> None:
    verdad = pl.read_parquet(RAIZ_FIXTURES / "verdad.parquet")
    filas_mojibake = verdad.filter(pl.col("mojibake_aplicado")).head(20)
    relatos_csv = pl.read_csv(RAIZ_FIXTURES / "relatos_sinteticos.csv", infer_schema_length=0)

    # Una noticia puede tener varios relatos (cardinalidad N); como el CSV no conserva
    # relato_id, se busca entre los candidatos de esa noticia el que reproduce exactamente el
    # texto original, en vez de asumir una correspondencia posicional que no existe.
    n_verificados = 0
    for fila in filas_mojibake.iter_rows(named=True):
        texto_original = fila["texto_antes_de_mojibake"]
        corrupto = relatos_csv.filter(relatos_csv["CASO_NOTICIA"] == fila["caso_noticia"])["RELATO"]
        candidatos = [t for t in corrupto.to_list() if t and tiene_mojibake(t)]
        resultados = [verificar_reparacion_mojibake(c) for c in candidatos]
        coincide = any(r.sin_residuo and r.reparado == texto_original for r in resultados)
        if not candidatos:
            continue
        assert coincide, "ningún candidato de esta noticia reproduce el texto original"
        n_verificados += 1
    assert n_verificados > 0


def test_es_mayuscula_sostenida() -> None:
    assert es_mayuscula_sostenida("TODO EN MAYUSCULAS SOSTENIDAS")
    assert not es_mayuscula_sostenida("Texto normal con minusculas")
    assert not es_mayuscula_sostenida("")


def test_detectar_posible_truncamiento() -> None:
    longitudes = [100, 200, 500, 500, 500, 500, 500]
    resumen = detectar_posible_truncamiento(longitudes, umbral_fraccion=0.3)
    assert resumen.longitud_maxima == 500
    assert resumen.posible_truncamiento is True

    longitudes_sin_pico = [100, 150, 200, 250, 300]
    resumen2 = detectar_posible_truncamiento(longitudes_sin_pico, umbral_fraccion=0.3)
    assert resumen2.posible_truncamiento is False


def test_contar_y_enmascarar_patrones_personales() -> None:
    texto = (
        "Se identifica a JUAN PEREZ, C.C. 1234567890, telefono 3001234567, "
        "correo juan@correo-ficticio.example y vehiculo de placas ABC123."
    )
    conteo = contar_patrones_personales(texto)
    assert conteo["cedula"] == 1
    assert conteo["telefono"] == 1
    assert conteo["correo"] == 1
    assert conteo["placa"] == 1

    enmascarado = enmascarar_basico(texto)
    assert "1234567890" not in enmascarado
    assert "3001234567" not in enmascarado
    assert "juan@correo-ficticio.example" not in enmascarado
    assert "ABC123" not in enmascarado
    assert "[DOC]" in enmascarado and "[TELEFONO]" in enmascarado and "[CORREO]" in enmascarado


def test_casi_duplicados_solo_entre_noticias_distintas() -> None:
    texto_base = "el denunciante refiere contrabando de mercancia en la bodega del municipio hoy"
    relatos = [
        ("R1", "N1", texto_base),
        ("R2", "N1", texto_base),  # mismo caso_noticia: no debe contar
        ("R3", "N2", texto_base),  # casi-idéntico, noticia distinta: sí debe contar
        ("R4", "N3", "un texto completamente distinto sobre captacion ilegal de dinero publico"),
    ]
    pares = detectar_casi_duplicados_entre_noticias(relatos, umbral=0.5)
    claves = {(p.id_a, p.id_b) for p in pares}
    assert ("R1", "R3") in claves
    assert ("R1", "R2") not in claves
    assert not any("R4" in (p.id_a, p.id_b) for p in pares)
