from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.ingesta.lote import procesar_lote

COLUMNAS = [
    "CASO_NOTICIA", "CASO_ID", "DESP_ID", "ESTADO", "ETAPA", "FECHA_HECHO", "FECHA_CREACION",
    "DELITO", "DEPARTAMENTO_HECHOS", "MUNICIPIO_HECHOS",
]


def _escribir_csv(ruta: Path, filas: list[dict[str, str]]) -> None:
    with ruta.open("w", encoding="utf-8") as f:
        f.write(",".join(COLUMNAS) + "\n")
        for fila in filas:
            f.write(",".join(fila[c] for c in COLUMNAS) + "\n")


def _fila(caso_notica: str, etapa: str = "INDAGACION") -> dict[str, str]:
    return {
        "CASO_NOTICIA": caso_notica,
        "CASO_ID": caso_notica,
        "DESP_ID": "D1",
        "ESTADO": "ACTIVO",
        "ETAPA": etapa,
        "FECHA_HECHO": "1/1/2026",
        "FECHA_CREACION": "2/1/2026",
        "DELITO": "LAVADO DE ACTIVOS ART. 323 C.P.",
        "DEPARTAMENTO_HECHOS": "BOGOTA",
        "MUNICIPIO_HECHOS": "BOGOTA",
    }


def test_procesar_lote_clasifica_y_calcula_deriva_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)

    # Lote 1: dos casos.
    archivo_1 = tmp_path / "CASOS_lote1.csv"
    _escribir_csv(archivo_1, [_fila("1"), _fila("2")])
    procesar_lote(conexion, archivo_1, "LOTE1", tmp_path / "lotes")

    # Lote 2: caso 1 repetido igual, caso 2 con ETAPA modificada, caso 3 nuevo.
    archivo_2 = tmp_path / "CASOS_lote2.csv"
    _escribir_csv(archivo_2, [_fila("1"), _fila("2", etapa="JUICIO"), _fila("3")])
    resumen = procesar_lote(conexion, archivo_2, "LOTE2", tmp_path / "lotes")

    assert resumen.n_nuevos == 1
    assert resumen.n_repetidos == 1
    assert resumen.n_modificados == 1
    assert resumen.n_validas == 3
    assert resumen.n_cuarentena == 0

    historico = conexion.sql("SELECT * FROM meta.historico_cambios").pl()
    assert historico.height == 1
    assert historico["caso_notica"].to_list() == ["2"]
    assert historico["campo"].to_list() == ["ETAPA"]
    assert historico["valor_anterior"].to_list() == ["INDAGACION"]
    assert historico["valor_nuevo"].to_list() == ["JUICIO"]
    conexion.close()


def test_procesar_lote_fila_sin_columna_obligatoria_va_a_cuarentena(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    archivo = tmp_path / "CASOS_malo.csv"
    # Falta DELITO (columna obligatoria) en la segunda fila.
    fila_2_sin_delito = {**_fila("2"), "DELITO": ""}
    with archivo.open("w", encoding="utf-8") as f:
        f.write(",".join(COLUMNAS) + "\n")
        f.write(",".join(_fila("1")[c] for c in COLUMNAS) + "\n")
        f.write(",".join(fila_2_sin_delito[c] for c in COLUMNAS) + "\n")

    resumen = procesar_lote(conexion, archivo, "LOTE1", tmp_path / "lotes")
    assert resumen.n_validas == 1
    assert resumen.n_cuarentena == 1

    cuarentena = conexion.sql("SELECT * FROM plata.cuarentena").pl()
    assert cuarentena.height == 1
    conexion.close()
