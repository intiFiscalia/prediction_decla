import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.emergencia.orquestador import ALERTA, CANDIDATO, procesar_emergencia

UMBRALES = {
    "cusum_k": 0.5,
    "cusum_h": 4.0,
    "farrington_umbral_desviaciones": 2.58,
    "fdr_maximo": 0.10,
    "persistencia_minima_periodos": 2,
    "tamanio_minimo_absoluto": 5,
    "minimo_unidades_registradoras": 2,
}


def _conexion_con_pico(
    n_desp_ids: int, ultimo_periodo_n: int, meses_con_pico: tuple[int, ...] = (6,)
) -> duckdb.DuckDBPyConnection:
    """Serie estable (~3 relatos/mes del fenómeno "x", repartidos en `n_desp_ids` despachos)
    durante 6 meses, con un salto fuerte a `ultimo_periodo_n` relatos de "x" en los meses listados
    en `meses_con_pico` (persistencia §8.5: un solo mes de pico no basta para "alerta", se queda
    en "candidato"; ≥2 meses consecutivos sí cumple persistencia mínima).

    Se agrega un fenómeno de fondo "y" (20 relatos/mes, estable, siempre en 20 despachos
    distintos) para que `volumen_total` (el offset) no sea trivialmente proporcional al conteo
    de "x" — si "x" fuera el único fenómeno del territorio, cualquier aumento de "x" se vería
    como "más volumen general" y el offset lo cancelaría por diseño (correcto: así se evita que
    un aumento general de registros dispare una señal por sí solo, plan §8.5). Con "y" de fondo,
    un salto de "x" sí cambia la proporción x/volumen_total de forma detectable.
    """
    conexion = duckdb.connect(":memory:")
    relatos, registros, asignacion = [], [], []
    contador = 0
    for mes in range(1, 7):
        n_mes_x = ultimo_periodo_n if mes in meses_con_pico else 3
        for i in range(n_mes_x):
            uid = f"uid_x_{contador}"
            caso = f"caso_x_{contador}"
            contador += 1
            relatos.append({"registro_uid": uid, "caso_notica": caso})
            registros.append(
                {
                    "caso_notica": caso, "cod_dpto_hechos": "11",
                    "desp_id": f"D{i % n_desp_ids}",
                    "fecha_creacion": f"2026-{mes:02d}-{(i % 27) + 1:02d}",
                    "anio_iso_creacion": 2026, "mes_creacion": mes,
                    "fecha_creacion_valida": True,
                }
            )
            asignacion.append({"registro_uid": uid, "codigo_fenomeno": "x"})
        for i in range(20):
            uid = f"uid_y_{contador}"
            caso = f"caso_y_{contador}"
            contador += 1
            relatos.append({"registro_uid": uid, "caso_notica": caso})
            registros.append(
                {
                    "caso_notica": caso, "cod_dpto_hechos": "11",
                    "desp_id": f"Dy{i}",
                    "fecha_creacion": f"2026-{mes:02d}-{(i % 27) + 1:02d}",
                    "anio_iso_creacion": 2026, "mes_creacion": mes,
                    "fecha_creacion_valida": True,
                }
            )
            asignacion.append({"registro_uid": uid, "codigo_fenomeno": "y"})
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    return conexion


def test_procesar_emergencia_detecta_alerta_con_pico_persistente() -> None:
    conexion = _conexion_con_pico(n_desp_ids=5, ultimo_periodo_n=30, meses_con_pico=(5, 6))
    resumen = procesar_emergencia(conexion, run_id="r1", umbrales=UMBRALES)
    assert resumen.n_series_evaluadas >= 1
    assert resumen.n_alertas >= 1

    alertas = conexion.sql("SELECT * FROM oro.alertas WHERE estado = ?", params=[ALERTA]).pl()
    assert alertas.height >= 1
    assert alertas["codigo_fenomeno"].to_list()[0] == "x"
    conexion.close()


def test_procesar_emergencia_pico_de_un_solo_mes_queda_como_candidato() -> None:
    """Un solo mes de exceso no cumple la persistencia mínima (≥2 periodos, plan §8.5): se
    registra como señal estadística, pero no se declara "alerta" todavía.
    """
    conexion = _conexion_con_pico(n_desp_ids=5, ultimo_periodo_n=30, meses_con_pico=(6,))
    resumen = procesar_emergencia(conexion, run_id="r1b", umbrales=UMBRALES)
    assert resumen.n_alertas == 0
    assert resumen.n_candidatos >= 1
    estados = conexion.sql("SELECT DISTINCT estado FROM oro.alertas").pl()["estado"].to_list()
    assert CANDIDATO in estados
    conexion.close()


def test_procesar_emergencia_concentrado_en_una_unidad_no_es_alerta() -> None:
    conexion = _conexion_con_pico(
        n_desp_ids=1, ultimo_periodo_n=30, meses_con_pico=(5, 6)
    )  # todo del mismo despacho, igual persistente en el tiempo
    resumen = procesar_emergencia(conexion, run_id="r2", umbrales=UMBRALES)
    assert resumen.n_alertas == 0
    assert resumen.n_descartadas_por_artefacto >= 1
    conexion.close()


def test_procesar_emergencia_pico_pequeno_queda_como_candidato() -> None:
    conexion = _conexion_con_pico(
        n_desp_ids=5, ultimo_periodo_n=8, meses_con_pico=(5, 6)
    )  # exceso real y persistente, pero < tamaño mínimo
    umbrales_tamanio_alto = {**UMBRALES, "tamanio_minimo_absoluto": 50}
    resumen = procesar_emergencia(conexion, run_id="r3", umbrales=umbrales_tamanio_alto)
    assert resumen.n_alertas == 0  # tamaño mínimo (50) nunca se alcanza: no puede forzarse alerta
    if resumen.n_candidatos:
        estados = conexion.sql("SELECT DISTINCT estado FROM oro.alertas").pl()["estado"].to_list()
        assert CANDIDATO in estados
    conexion.close()


def test_procesar_emergencia_sin_datos_no_falla() -> None:
    conexion = duckdb.connect(":memory:")
    conexion.execute("CREATE SCHEMA fenomenos")
    conexion.execute(
        "CREATE TABLE fenomenos.asignacion_fenomeno (registro_uid VARCHAR, codigo_fenomeno VARCHAR)"
    )
    resumen = procesar_emergencia(conexion, run_id="r4", umbrales=UMBRALES)
    assert resumen.n_series_evaluadas == 0
    conexion.close()
