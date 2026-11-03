import duckdb

from decla.analitica.asociaciones import (
    chi2_fenomeno_delito,
    consolidar_con_correccion_multiple,
    fila_estandar,
    poisson_o_nb_offset,
    red_coocurrencia_menciones,
    reglas_asociacion_fenomeno_sector_territorio,
)
from decla.comun.duckdb_io import escribir_tabla_polars


def _conexion_base(n_por_fenomeno: int = 20) -> duckdb.DuckDBPyConnection:
    """Dos fenómenos claramente asociados a delitos distintos, repartidos en 2 territorios y 2
    periodos, con menciones de sector y mecanismo para las reglas de asociación / co-ocurrencia.
    """
    conexion = duckdb.connect(":memory:")
    relatos, registros, asignacion, menciones = [], [], [], []
    for i in range(n_por_fenomeno):
        uid = f"uid_a_{i}"
        caso = f"caso_a_{i}"
        relatos.append({"registro_uid": uid, "caso_notica": caso})
        registros.append(
            {
                "caso_notica": caso, "delito_nombre": "LAVADO DE ACTIVOS",
                "cod_dpto_hechos": "11" if i % 2 == 0 else "05",
                "anio_iso_creacion": 2026,
                "mes_creacion": 1 if i < n_por_fenomeno // 2 else 2,
                "fecha_creacion_valida": True,
            }
        )
        asignacion.append({"registro_uid": uid, "codigo_fenomeno": "lavado_de_activos"})
        menciones.append(
            {
                "registro_uid": uid, "categoria": "sector", "subcategoria": None,
                "valor_normalizado": "4661", "polaridad": "afirmada",
            }
        )
        # Co-ocurre siempre con este mecanismo (afirmado): debe quedar como arista en la red.
        menciones.append(
            {
                "registro_uid": uid, "categoria": "mecanismo", "subcategoria": None,
                "valor_normalizado": "testaferros", "polaridad": "afirmada",
            }
        )
    for i in range(n_por_fenomeno):
        uid = f"uid_b_{i}"
        caso = f"caso_b_{i}"
        relatos.append({"registro_uid": uid, "caso_notica": caso})
        registros.append(
            {
                "caso_notica": caso, "delito_nombre": "CONTRABANDO",
                "cod_dpto_hechos": "11" if i % 2 == 0 else "05",
                "anio_iso_creacion": 2026,
                "mes_creacion": 1 if i < n_por_fenomeno // 2 else 2,
                "fecha_creacion_valida": True,
            }
        )
        asignacion.append({"registro_uid": uid, "codigo_fenomeno": "organizacion_criminal"})
        menciones.append(
            {
                "registro_uid": uid, "categoria": "mecanismo", "subcategoria": None,
                "valor_normalizado": "contrabando_tecnico", "polaridad": "afirmada",
            }
        )
        # Mención negada: debe excluirse de la red de co-ocurrencia (no debería generar arista
        # con mecanismo:contrabando_tecnico aunque comparta registro_uid).
        menciones.append(
            {
                "registro_uid": uid, "categoria": "sector", "subcategoria": None,
                "valor_normalizado": "4661", "polaridad": "negada",
            }
        )

    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    escribir_tabla_polars(conexion, "texto", "menciones", menciones)
    return conexion


def test_chi2_fenomeno_delito_detecta_asociacion_perfecta() -> None:
    conexion = _conexion_base()
    resultado = chi2_fenomeno_delito(conexion)
    assert resultado["calculado"] is True
    assert resultado["p"] < 0.01  # fenómeno y delito coinciden perfectamente por construcción
    assert resultado["tamanio_efecto_v_cramer"] is not None
    assert resultado["n"] == 40
    conexion.close()


def test_chi2_fenomeno_delito_usa_fisher_si_esperadas_bajas() -> None:
    conexion = _conexion_base(n_por_fenomeno=3)  # celdas pequeñas -> esperadas < 5 en 2x2
    resultado = chi2_fenomeno_delito(conexion)
    assert resultado["calculado"] is True
    assert resultado["metodo"] == "fisher_exacto"
    conexion.close()


def test_reglas_asociacion_encuentra_fenomeno_sector() -> None:
    conexion = _conexion_base()
    reglas = reglas_asociacion_fenomeno_sector_territorio(
        conexion, soporte_minimo=0.1, confianza_minima=0.5
    )
    assert reglas.height > 0
    pares = set(zip(reglas["antecedents"].to_list(), reglas["consequents"].to_list(), strict=True))
    assert any("fenomeno=lavado_de_activos" in a and "sector=4661" in c for a, c in pares) or any(
        "sector=4661" in a and "fenomeno=lavado_de_activos" in c for a, c in pares
    )
    conexion.close()


def test_poisson_o_nb_offset_con_suficientes_celdas() -> None:
    conexion = _conexion_base()
    resultado = poisson_o_nb_offset(conexion)
    assert resultado["calculado"] is True
    assert resultado["metodo"] in {"poisson", "binomial_negativa"}
    assert resultado["n_observaciones"] > 0
    conexion.close()


def test_poisson_o_nb_offset_insuficientes_celdas() -> None:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion, "texto", "relato_procesado", [{"registro_uid": "uid_1", "caso_notica": "c1"}]
    )
    escribir_tabla_polars(
        conexion,
        "plata",
        "registros_limpios",
        [
            {
                "caso_notica": "c1", "cod_dpto_hechos": "11",
                "anio_iso_creacion": 2026, "mes_creacion": 1, "fecha_creacion_valida": True,
            }
        ],
    )
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [{"registro_uid": "uid_1", "codigo_fenomeno": "x"}],
    )
    # Un solo territorio y un solo periodo: no hay suficientes celdas para efectos fijos de ambos.
    resultado = poisson_o_nb_offset(conexion)
    assert resultado["calculado"] is False
    conexion.close()


def test_red_coocurrencia_excluye_negadas() -> None:
    conexion = _conexion_base()
    resultado = red_coocurrencia_menciones(conexion)
    assert resultado["calculado"] is True
    grafo = resultado["grafo"]
    # sector:4661 (afirmado en uid_a) co-ocurre siempre con mecanismo:testaferros -> arista real.
    assert grafo.has_edge("sector:4661", "mecanismo:testaferros")
    # mecanismo:contrabando_tecnico solo compartiría registro_uid con sector:4661 vía la mención
    # *negada* de uid_b; al excluirla, no debe quedar ninguna arista hacia ese nodo.
    assert not grafo.has_node("mecanismo:contrabando_tecnico") or (
        grafo.degree("mecanismo:contrabando_tecnico") == 0
    )
    conexion.close()


def test_consolidar_con_correccion_multiple_ajusta_p() -> None:
    filas = [
        fila_estandar("a,b", "chi2", 1.0, 0.1, (0.0, 0.2), 0.01, 10),
        fila_estandar("c,d", "chi2", 1.0, 0.1, (0.0, 0.2), 0.04, 10),
        fila_estandar("e,f", "chi2", 1.0, 0.1, (0.0, 0.2), 0.5, 10),
    ]
    resultado = consolidar_con_correccion_multiple(filas)
    assert all(f["p_ajustado_bh"] is not None for f in resultado)
    assert resultado[0]["p_ajustado_bh"] >= resultado[0]["p"]  # BH nunca reduce el p-valor
