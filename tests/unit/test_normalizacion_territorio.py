from decla.calidad.territorio import EntradaDivipola
from decla.normalizacion.territorio import cargar_excepciones_manuales, emparejar_con_manual

DIVIPOLA_PRUEBA = [
    EntradaDivipola("50", "50001", "META", "VILLAVICENCIO"),
]


def test_cargar_excepciones_manuales_vacio() -> None:
    assert cargar_excepciones_manuales({"excepciones": []}) == {}
    assert cargar_excepciones_manuales({}) == {}


def test_cargar_excepciones_manuales_indexa_por_valores_originales() -> None:
    contenido = {
        "excepciones": [
            {
                "departamento_original": "XYZ",
                "municipio_original": "PUEBLO_RARO",
                "cod_dpto": "50",
                "cod_mpio": "50001",
                "nota": "confirmado por analista",
            }
        ]
    }
    excepciones = cargar_excepciones_manuales(contenido)
    assert ("XYZ", "PUEBLO_RARO") in excepciones
    assert excepciones[("XYZ", "PUEBLO_RARO")].cod_mpio == "50001"


def test_emparejar_con_manual_usa_automatico_si_resuelve() -> None:
    resultado = emparejar_con_manual("META", "VILLAVICENCIO", DIVIPOLA_PRUEBA, {})
    assert resultado.metodo == "exacto"


def test_emparejar_con_manual_usa_excepcion_si_no_resoluble() -> None:
    excepciones = cargar_excepciones_manuales(
        {
            "excepciones": [
                {
                    "departamento_original": "XYZ",
                    "municipio_original": "PUEBLO_RARO",
                    "cod_dpto": "50",
                    "cod_mpio": "50001",
                }
            ]
        }
    )
    resultado = emparejar_con_manual("XYZ", "PUEBLO_RARO", DIVIPOLA_PRUEBA, excepciones)
    assert resultado.metodo == "manual"
    assert resultado.cod_mpio == "50001"
    assert resultado.confianza == 1.0


def test_emparejar_con_manual_sigue_no_resoluble_sin_excepcion() -> None:
    resultado = emparejar_con_manual("XYZ", "PUEBLO_RARO", DIVIPOLA_PRUEBA, {})
    assert resultado.metodo == "no_resoluble"
