from decla.entidades.noticia import (
    construir_caso,
    construir_grupo_conexo,
    construir_noticia_criminal,
    construir_puente_noticia_delito,
    construir_puente_registro_noticia_caso,
)

FILAS = [
    {
        "registro_uid": "u1",
        "caso_notica": "N1",
        "caso_id": "C1",
        "cod_dpto_hechos": "50",
        "cod_mpio_hechos": "50001",
        "cod_dpto_unidad": "50",
        "cod_mpio_unidad": "50001",
        "fecha_hecho": "2026-01-01",
        "fecha_creacion": "2026-01-02",
        "estado_norm": "ACTIVO",
        "etapa_norm": "INDAGACION",
        "no_casos_conexos": "2",
        "delito_nombre": "LAVADO DE ACTIVOS",
        "articulo_cp": "323",
    },
    {
        "registro_uid": "u2",
        "caso_notica": "N2",
        "caso_id": "C2",
        "cod_dpto_hechos": "11",
        "cod_mpio_hechos": "11001",
        "cod_dpto_unidad": "11",
        "cod_mpio_unidad": "11001",
        "fecha_hecho": "2026-02-01",
        "fecha_creacion": "2026-02-02",
        "estado_norm": "ACTIVO",
        "etapa_norm": "INDAGACION",
        "no_casos_conexos": None,
        "delito_nombre": None,
        "articulo_cp": None,
    },
]


def test_construir_noticia_criminal_una_fila_por_noticia() -> None:
    noticias = construir_noticia_criminal(FILAS)
    assert len(noticias) == 2
    assert {n["caso_notica"] for n in noticias} == {"N1", "N2"}


def test_construir_noticia_criminal_deduplica_si_se_repite_noticia() -> None:
    filas_con_duplicado = FILAS + [FILAS[0]]
    noticias = construir_noticia_criminal(filas_con_duplicado)
    assert len(noticias) == 2


def test_construir_caso_mismo_grano() -> None:
    casos = construir_caso(FILAS)
    assert len(casos) == 2
    assert {c["caso_id"] for c in casos} == {"C1", "C2"}


def test_construir_puente_noticia_delito_omite_sin_delito() -> None:
    puente = construir_puente_noticia_delito(FILAS)
    assert len(puente) == 1
    assert puente[0]["caso_notica"] == "N1"
    assert puente[0]["delito_nombre"] == "LAVADO DE ACTIVOS"


def test_construir_puente_registro_noticia_caso() -> None:
    puente = construir_puente_registro_noticia_caso(FILAS)
    assert len(puente) == 2
    assert puente[0] == {"registro_uid": "u1", "caso_notica": "N1", "caso_id": "C1"}


def test_construir_grupo_conexo_declarado_vs_sin_declarar() -> None:
    grupos = construir_grupo_conexo(FILAS)
    por_noticia = {g["caso_notica"]: g for g in grupos}
    assert por_noticia["N1"]["tiene_conexos_declarados"] is True
    assert por_noticia["N1"]["no_casos_conexos_declarados"] == "2"
    assert por_noticia["N2"]["tiene_conexos_declarados"] is False
    assert por_noticia["N2"]["no_casos_conexos_declarados"] is None


def test_construir_grupo_conexo_cero_no_es_conexo() -> None:
    filas = [{**FILAS[0], "no_casos_conexos": "0"}]
    grupos = construir_grupo_conexo(filas)
    assert grupos[0]["tiene_conexos_declarados"] is False
