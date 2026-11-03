import numpy as np

from decla.fenomenos.orquestador import _codigo_grupo, _grupos_por_etiqueta


def test_codigo_grupo_antepone_el_metodo() -> None:
    assert _codigo_grupo("hdbscan", 0) == "hdbscan_0"
    assert _codigo_grupo("nmf", 3) == "nmf_3"
    assert _codigo_grupo("agglomerative", 2) == "agglomerative_2"


def test_grupos_por_etiqueta_sin_excluir_ruido() -> None:
    uids = ["a", "b", "c"]
    etiquetas = np.array([0, 1, 0])
    grupos = _grupos_por_etiqueta(uids, etiquetas, "nmf", excluir_ruido=False)
    assert grupos == {"nmf_0": ["a", "c"], "nmf_1": ["b"]}


def test_grupos_por_etiqueta_excluye_ruido_solo_si_se_pide() -> None:
    uids = ["a", "b", "c"]
    etiquetas = np.array([0, -1, 0])
    grupos = _grupos_por_etiqueta(uids, etiquetas, "hdbscan", excluir_ruido=True)
    assert grupos == {"hdbscan_0": ["a", "c"]}
    assert "hdbscan_-1" not in grupos


def test_grupos_por_etiqueta_sin_excluir_ruido_incluye_la_etiqueta_de_ruido() -> None:
    uids = ["a", "b"]
    etiquetas = np.array([0, -1])
    grupos = _grupos_por_etiqueta(uids, etiquetas, "hdbscan", excluir_ruido=False)
    assert grupos == {"hdbscan_0": ["a"], "hdbscan_-1": ["b"]}


def test_grupos_por_etiqueta_metodos_distintos_no_colisionan() -> None:
    uids = ["a", "b"]
    etiquetas = np.array([0, 0])
    grupos_nmf = _grupos_por_etiqueta(uids, etiquetas, "nmf", excluir_ruido=False)
    grupos_hdbscan = _grupos_por_etiqueta(uids, etiquetas, "hdbscan", excluir_ruido=False)
    assert set(grupos_nmf) != set(grupos_hdbscan)
    assert "nmf_0" in grupos_nmf
    assert "hdbscan_0" in grupos_hdbscan
