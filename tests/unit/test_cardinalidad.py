from pathlib import Path

import polars as pl

from decla.calidad.cardinalidad import (
    proponer_hipotesis_grano,
    resumir_cardinalidad,
    resumir_union,
    verificar_hipotesis_caso_noticia,
)
from decla.ingesta.lectores import TablaLeida, leer_csv

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _tabla(filas: list[dict]) -> TablaLeida:
    columnas = list(filas[0]) if filas else []
    return TablaLeida(
        nombre="prueba",
        columnas=columnas,
        filas=filas,
        fila_origen=list(range(2, 2 + len(filas))),
        n_filas_total=len(filas),
        n_filas_vacias=0,
    )


def _fila(caso_id, caso_noticia, delito="X", despacho="D1", fecha_asig="1/1/2026", ultima="A"):
    return {
        "CASO_ID": caso_id,
        "CASO_NOTICIA": caso_noticia,
        "DELITO": delito,
        "DESPACHO": despacho,
        "FECHA_ASIGNACION": fecha_asig,
        "ULTIMA_ACTUACION": ultima,
    }


def test_resumir_cardinalidad_detecta_duplicado_exacto() -> None:
    fila = _fila("1", "N1")
    tabla = _tabla([fila, dict(fila), _fila("2", "N2")])
    resumen = resumir_cardinalidad(tabla)
    assert resumen.n_filas == 3
    assert resumen.n_caso_noticia_unicos == 2
    assert resumen.n_duplicados_exactos == 1
    assert resumen.n_duplicados_parciales == 0


def test_resumir_cardinalidad_detecta_duplicado_parcial_multidelito() -> None:
    tabla = _tabla(
        [
            _fila("1", "N1", delito="LAVADO"),
            _fila("1", "N1", delito="CONTRABANDO"),
            _fila("2", "N2"),
        ]
    )
    resumen = resumir_cardinalidad(tabla)
    assert resumen.n_duplicados_parciales == 1
    assert resumen.distribucion_filas_por_noticia == {2: 1, 1: 1}


def test_resumir_union_clasifica_coincidencias_huerfanos_y_sin_relato() -> None:
    tabla_casos = _tabla([_fila("1", "N1"), _fila("2", "N2"), _fila("3", "N3")])
    tabla_relatos = TablaLeida(
        nombre="relatos",
        columnas=["CASO_NOTICIA", "RELATO"],
        filas=[
            {"CASO_NOTICIA": "N1", "RELATO": "texto 1"},
            {"CASO_NOTICIA": "N1", "RELATO": "texto 1 bis"},
            {"CASO_NOTICIA": "N_HUERFANA", "RELATO": "texto huerfano"},
        ],
        fila_origen=[2, 3, 4],
        n_filas_total=3,
        n_filas_vacias=0,
    )
    resumen = resumir_union(tabla_casos, tabla_relatos)
    assert resumen.n_noticias_casos == 3
    assert resumen.n_coincidencias == 1
    assert resumen.n_huerfanos_relatos == 1
    assert resumen.n_casos_sin_relato == 2
    assert resumen.distribucion_relatos_por_noticia == {2: 1, 1: 1}


def _caso_noticia(cod_mpio: str = "11001", entidad: str = "17", unidad: str = "00002",
                   anio: str = "2026", consecutivo: str = "00001") -> str:
    valor = cod_mpio + entidad + unidad + anio + consecutivo
    assert len(valor) == 21, f"construcción de prueba inválida: {valor!r}, {len(valor)} dígitos"
    return valor


def test_verificar_hipotesis_caso_noticia_longitud_y_prefijo_y_anio() -> None:
    tabla = _tabla(
        [
            {"CASO_NOTICIA": _caso_noticia()[:-1], "FECHA_CREACION": "1/1/2026"},  # 20 dígitos
            {"CASO_NOTICIA": _caso_noticia(), "FECHA_CREACION": "1/1/2026"},  # 21, válido
            {"CASO_NOTICIA": _caso_noticia(cod_mpio="99999"), "FECHA_CREACION": "1/1/2026"},
            {"CASO_NOTICIA": _caso_noticia(anio="2025"), "FECHA_CREACION": "1/1/2026"},
        ]
    )
    resumen = verificar_hipotesis_caso_noticia(tabla, cod_mpios_validos={"11001"})
    assert resumen.n_total == 4
    assert resumen.n_longitud_21 == 3
    assert resumen.n_prefijo_dane_valido == 2
    assert resumen.n_anio_coincide == 2  # el de prefijo inválido también tiene año correcto


def test_proponer_hipotesis_grano_devuelve_rankeadas_con_evidencia() -> None:
    tabla = _tabla(
        [
            _fila("1", "N1", delito="LAVADO"),
            _fila("1", "N1", delito="CONTRABANDO"),
            _fila("2", "N2"),
            _fila("3", "N3"),
        ]
    )
    resumen = resumir_cardinalidad(tabla)
    hipotesis = proponer_hipotesis_grano(resumen)
    assert len(hipotesis) == 3
    assert hipotesis[0].puntaje >= hipotesis[1].puntaje >= hipotesis[2].puntaje
    assert all(h.evidencia for h in hipotesis)


def test_cardinalidad_y_union_contra_fixtures_reales() -> None:
    tabla_casos = leer_csv(RAIZ_FIXTURES / "casos_sinteticos.csv")
    tabla_relatos = leer_csv(RAIZ_FIXTURES / "relatos_sinteticos.csv")

    resumen_card = resumir_cardinalidad(tabla_casos)
    assert resumen_card.n_caso_noticia_unicos > 0
    assert resumen_card.n_duplicados_exactos > 0  # el generador planta duplicados exactos

    resumen_union = resumir_union(tabla_casos, tabla_relatos)
    assert resumen_union.n_coincidencias > 0
    assert resumen_union.n_huerfanos_relatos > 0
    assert resumen_union.n_casos_sin_relato > 0

    divipola = pl.read_csv(RAIZ_FIXTURES / "divipola_sintetico.csv", infer_schema_length=0)
    cod_mpios = set(divipola["cod_mpio"].to_list())
    resumen_cn = verificar_hipotesis_caso_noticia(tabla_casos, cod_mpios)
    assert resumen_cn.n_total > 0
    assert 0 < resumen_cn.pct_longitud_21 <= 100
