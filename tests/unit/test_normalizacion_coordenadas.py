from pathlib import Path

from shapely.geometry import Polygon

from decla.normalizacion.coordenadas import cargar_geometrias_municipios, clasificar_coordenada

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_CARTOGRAFIA = RAIZ_PROYECTO / "data" / "referencia" / "cartografia" / "municipios.geojson"

# Cuadrado alrededor de Villavicencio (4.142, -73.6266) para pruebas sin depender del geojson real.
GEOMETRIAS_PRUEBA = {
    "50001": Polygon([(-73.7, 4.0), (-73.7, 4.3), (-73.5, 4.3), (-73.5, 4.0)]),
}


def test_clasifica_vacia_como_faltante() -> None:
    resultado = clasificar_coordenada(None, None, "50001", None, GEOMETRIAS_PRUEBA)
    assert resultado.calidad_coord == "faltante"


def test_clasifica_reparada_escala_como_reparada_decimal() -> None:
    resultado = clasificar_coordenada(
        "LAT 4142", "LONG -736266", "50001", None, GEOMETRIAS_PRUEBA
    )
    assert resultado.calidad_coord == "reparada_decimal"


def test_clasifica_invertida_como_invertida_corregida() -> None:
    resultado = clasificar_coordenada("-73.6266", "4.142", "50001", None, GEOMETRIAS_PRUEBA)
    assert resultado.calidad_coord == "invertida_corregida"


def test_clasifica_fuera_de_colombia_como_fuera_pais() -> None:
    resultado = clasificar_coordenada("40.4168", "-3.7038", "50001", None, GEOMETRIAS_PRUEBA)
    assert resultado.calidad_coord == "fuera_pais"


def test_clasifica_centroide() -> None:
    centroide = (4.142, -73.6266)
    resultado = clasificar_coordenada("4.142", "-73.6266", "50001", centroide, GEOMETRIAS_PRUEBA)
    assert resultado.calidad_coord == "centroide"


def test_clasifica_exacta_dentro_del_municipio() -> None:
    resultado = clasificar_coordenada(
        "4.14", "-73.62", "50001", (0.0, 0.0), GEOMETRIAS_PRUEBA
    )
    assert resultado.calidad_coord == "exacta"


def test_clasifica_fuera_municipio_si_cae_afuera_del_poligono_declarado() -> None:
    # Dentro de la caja de Colombia pero fuera del cuadrado de prueba de Villavicencio.
    resultado = clasificar_coordenada(
        "10.0", "-74.0", "50001", (0.0, 0.0), GEOMETRIAS_PRUEBA
    )
    assert resultado.calidad_coord == "fuera_municipio"


def test_clasifica_exacta_sin_geometria_conocida() -> None:
    resultado = clasificar_coordenada("4.14", "-73.62", "99999", (0.0, 0.0), GEOMETRIAS_PRUEBA)
    assert resultado.calidad_coord == "exacta"


def test_cargar_geometrias_municipios_contra_cartografia_real() -> None:
    geometrias = cargar_geometrias_municipios(RUTA_CARTOGRAFIA)
    assert "11001" in geometrias  # Bogotá
    assert geometrias["11001"].is_valid


def test_clasificar_coordenada_contra_cartografia_real_bogota() -> None:
    geometrias = cargar_geometrias_municipios(RUTA_CARTOGRAFIA)
    # Punto dentro de Bogotá (Plaza de Bolívar, aprox.)
    resultado = clasificar_coordenada(
        "4.5981", "-74.0758", "11001", (0.0, 0.0), geometrias
    )
    assert resultado.calidad_coord == "exacta"
