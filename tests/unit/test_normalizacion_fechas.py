from decla.calidad.fechas import FORMATO_AMBIGUO, FORMATO_MDY, detectar_formato_fecha
from decla.normalizacion.fechas import normalizar_columna_fecha


def test_normalizar_columna_fecha_valida() -> None:
    resultado = normalizar_columna_fecha(
        "FECHA_HECHO", ["3/25/2026", "1/5/2026"], valores_invalidos_conocidos=set()
    )
    assert resultado.formato_detectado == FORMATO_MDY
    assert resultado.fecha_valida == [True, True]
    assert resultado.fecha_imputada == [False, False]
    assert resultado.fecha_ausente == [False, False]
    assert resultado.motivo == [None, None]


def test_normalizar_columna_fecha_sentinel_queda_imputada() -> None:
    resultado = normalizar_columna_fecha(
        "FECHA_HECHO", ["3/25/2026", "1/1/1900"], valores_invalidos_conocidos={"1/1/1900"}
    )
    assert resultado.fecha_valida == [True, False]
    assert resultado.fecha_imputada == [False, True]
    assert resultado.valores[1] is None
    assert resultado.motivo[1] == "valor_sentinel_conocido"


def test_normalizar_columna_fecha_none_no_es_invalida_ni_imputada() -> None:
    resultado = normalizar_columna_fecha(
        "FECHA_HECHO", ["3/25/2026", None], valores_invalidos_conocidos=set()
    )
    assert resultado.fecha_valida == [True, False]
    assert resultado.fecha_imputada == [False, False]
    assert resultado.motivo == [None, None]


def test_normalizar_columna_fecha_none_queda_marcada_ausente_no_invalida() -> None:
    # Un valor ausente (None) no es un defecto de formato: el reporte de calidad debe poder
    # distinguirlo de "no_parseable" para no confundir "dato no diligenciado" con "dato corrupto"
    # (p. ej. FECHA_ULTIMA_ACTUACION vacía en una noticia sin actuaciones posteriores).
    resultado = normalizar_columna_fecha(
        "FECHA_ULTIMA_ACTUACION", ["3/25/2026", None, None], valores_invalidos_conocidos=set()
    )
    assert resultado.fecha_ausente == [False, True, True]
    assert resultado.fecha_valida == [True, False, False]
    assert resultado.fecha_imputada == [False, False, False]


def test_normalizar_columna_fecha_formato_ambiguo() -> None:
    # Ningún valor tiene >12 en alguna posición: no hay evidencia de formato.
    resultado = normalizar_columna_fecha(
        "FECHA_HECHO", ["1/1/2026", "2/2/2026"], valores_invalidos_conocidos=set()
    )
    assert resultado.formato_detectado == FORMATO_AMBIGUO
    assert resultado.fecha_valida == [False, False]
    assert resultado.motivo == ["formato_columna_ambiguo", "formato_columna_ambiguo"]


def test_normalizar_columna_fecha_no_parseable_con_formato_conocido() -> None:
    # "2/30/2026" aporta evidencia M/D/AAAA (30 en 2ª posición) pero no es una fecha válida
    # (30 de febrero no existe).
    resultado = normalizar_columna_fecha(
        "FECHA_HECHO", ["3/25/2026", "2/30/2026"], valores_invalidos_conocidos=set()
    )
    assert resultado.formato_detectado == FORMATO_MDY
    assert resultado.fecha_valida == [True, False]
    assert resultado.motivo[1] == "no_parseable"


def test_conteo_de_reporte_no_confunde_ausente_con_invalida() -> None:
    # Replica la aritmética de `orquestador._escribir_reporte_calidad`: n_invalidas debe excluir
    # tanto los sentinels imputados como los valores simplemente ausentes, para no reportar un
    # campo no diligenciado (p. ej. FECHA_ULTIMA_ACTUACION en una noticia sin más actuaciones)
    # como si fuera un defecto de formato.
    resultado = normalizar_columna_fecha(
        "FECHA_ULTIMA_ACTUACION",
        ["3/25/2026", None, None, "1/1/1900", "no-es-una-fecha-valida-mdy/99/9999"],
        valores_invalidos_conocidos={"1/1/1900"},
    )
    n_imputadas = sum(resultado.fecha_imputada)
    n_ausentes = sum(resultado.fecha_ausente)
    n_invalidas = sum(1 for v in resultado.fecha_valida if not v) - n_imputadas - n_ausentes

    assert n_imputadas == 1
    assert n_ausentes == 2
    assert n_invalidas == 1


def test_formato_forzado_evita_mala_deteccion_en_subconjunto_sesgado() -> None:
    # Población completa (p. ej. todas las filas válidas de un lote): evidencia clara de M/D/AAAA.
    poblacion_completa = ["3/25/2026", "1/13/2026", "5/20/2026", "7/4/2026"] * 10
    formato_poblacion = detectar_formato_fecha(poblacion_completa)[0]
    assert formato_poblacion == FORMATO_MDY

    # Subconjunto filtrado por alcance (p. ej. solo 2 filas): ninguna aporta evidencia de formato
    # por sí sola, así que detectarlo de nuevo sobre el subconjunto daría "ambiguo" y perdería
    # fechas válidas. Forzar el formato de la población completa corrige esto.
    subconjunto_sesgado = ["3/4/2026", "1/2/2026"]
    sin_forzar = normalizar_columna_fecha(
        "FECHA_HECHO", subconjunto_sesgado, valores_invalidos_conocidos=set()
    )
    assert sin_forzar.formato_detectado == FORMATO_AMBIGUO
    assert sin_forzar.fecha_valida == [False, False]

    forzado = normalizar_columna_fecha(
        "FECHA_HECHO",
        subconjunto_sesgado,
        valores_invalidos_conocidos=set(),
        formato_forzado=formato_poblacion,
    )
    assert forzado.formato_detectado == FORMATO_MDY
    assert forzado.fecha_valida == [True, True]
    assert forzado.motivo == [None, None]
