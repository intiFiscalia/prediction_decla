from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.ingesta.bronce import (
    calcular_registro_uid,
    copiar_inmutable,
    hash_archivo,
    ingerir_lote,
    ingerir_tabla,
)

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_hash_archivo_es_determinista(tmp_path: Path) -> None:
    ruta = tmp_path / "a.csv"
    ruta.write_text("A,B\n1,2\n", encoding="utf-8")
    assert hash_archivo(ruta) == hash_archivo(ruta)


def test_calcular_registro_uid_mismos_insumos_mismo_hash() -> None:
    fila = {"A": "1", "B": "2"}
    uid1 = calcular_registro_uid("LOTE1", "CASOS", 2, fila)
    uid2 = calcular_registro_uid("LOTE1", "CASOS", 2, dict(fila))
    assert uid1 == uid2


def test_calcular_registro_uid_cambia_con_lote_fila_o_contenido() -> None:
    base = calcular_registro_uid("LOTE1", "CASOS", 2, {"A": "1"})
    assert base != calcular_registro_uid("LOTE2", "CASOS", 2, {"A": "1"})
    assert base != calcular_registro_uid("LOTE1", "CASOS", 3, {"A": "1"})
    assert base != calcular_registro_uid("LOTE1", "CASOS", 2, {"A": "2"})


def test_calcular_registro_uid_no_depende_del_orden_de_columnas() -> None:
    uid1 = calcular_registro_uid("L1", "CASOS", 2, {"A": "1", "B": "2"})
    uid2 = calcular_registro_uid("L1", "CASOS", 2, {"B": "2", "A": "1"})
    assert uid1 == uid2


def test_copiar_inmutable_preserva_contenido(tmp_path: Path) -> None:
    origen = tmp_path / "origen" / "a.csv"
    origen.parent.mkdir(parents=True)
    origen.write_text("A,B\n1,2\n", encoding="utf-8")

    destino = copiar_inmutable(origen, tmp_path / "lotes", "LOTE1")
    assert destino.read_text(encoding="utf-8") == origen.read_text(encoding="utf-8")
    assert destino.parent.name == "LOTE1"


def test_ingerir_tabla_carga_con_linaje_y_registra_lote(tmp_path: Path) -> None:
    ruta = tmp_path / "casos.csv"
    ruta.write_text("A,B\n1,2\n3,4\n", encoding="utf-8")
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)

    resumen = ingerir_tabla(ruta, "CASOS", "LOTE1", conexion, "casos_raw")

    assert resumen.n_filas_cargadas == 2
    filas = conexion.execute(
        "SELECT registro_uid, lote_id, tabla_origen, n_fila, A, B "
        "FROM bronce.casos_raw ORDER BY n_fila"
    ).fetchall()
    assert len(filas) == 2
    assert filas[0][1:] == ("LOTE1", "CASOS", 2, "1", "2")
    assert all(f[0] for f in filas)  # registro_uid no vacío

    lotes = conexion.execute("SELECT lote_id, archivo, n_filas_cargadas FROM meta.lotes").fetchall()
    assert lotes == [("LOTE1", "casos.csv", 2)]
    conexion.close()


def test_ingerir_tabla_dos_lotes_se_acumulan(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)

    ruta1 = tmp_path / "casos1.csv"
    ruta1.write_text("A\n1\n", encoding="utf-8")
    ruta2 = tmp_path / "casos2.csv"
    ruta2.write_text("A\n2\n", encoding="utf-8")

    ingerir_tabla(ruta1, "CASOS", "LOTE1", conexion, "casos_raw")
    ingerir_tabla(ruta2, "CASOS", "LOTE2", conexion, "casos_raw")

    total = conexion.execute("SELECT count(*) FROM bronce.casos_raw").fetchone()[0]
    assert total == 2
    lotes = conexion.execute("SELECT count(*) FROM meta.lotes").fetchone()[0]
    assert lotes == 2
    conexion.close()


def test_ingerir_lote_extremo_a_extremo_con_fixtures(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    resumenes = ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE_PRUEBA", conexion)

    assert len(resumenes) == 2
    nombres_tabla = {r.tabla_destino for r in resumenes}
    assert nombres_tabla == {"bronce.casos_raw", "bronce.relatos_raw"}

    n_casos = conexion.execute("SELECT count(*) FROM bronce.casos_raw").fetchone()[0]
    n_relatos = conexion.execute("SELECT count(*) FROM bronce.relatos_raw").fetchone()[0]
    assert n_casos > 0
    assert n_relatos > 0

    copia = tmp_path / "lotes" / "LOTE_PRUEBA"
    assert any(p.name.startswith("casos") for p in copia.iterdir())
    assert any(p.name.startswith("relatos") for p in copia.iterdir())
    conexion.close()
