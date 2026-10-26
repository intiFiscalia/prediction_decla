"""Casi-duplicados vía MinHash/LSH (plan_trabajo.md §6.1 paso 10; CLAUDE.md §4-bis: 90 pares de
relatos casi-idénticos detectados en el diagnóstico real entre noticias DISTINTAS). Marca el
mismo hecho registrado varias veces para que 2C no lo cuente como evidencia repetida de un
fenómeno.
"""

from __future__ import annotations

from dataclasses import dataclass

from datasketch import MinHash, MinHashLSH

N_PERMUTACIONES = 128
TAMANO_SHINGLE = 5


def _shingles(texto: str, tamano: int = TAMANO_SHINGLE) -> set[str]:
    palabras = texto.lower().split()
    if len(palabras) < tamano:
        return {" ".join(palabras)} if palabras else set()
    return {" ".join(palabras[i : i + tamano]) for i in range(len(palabras) - tamano + 1)}


def calcular_minhash(texto: str, n_permutaciones: int = N_PERMUTACIONES) -> MinHash:
    mh = MinHash(num_perm=n_permutaciones)
    for shingle in _shingles(texto):
        mh.update(shingle.encode("utf-8"))
    return mh


@dataclass(frozen=True)
class ParCasiDuplicado:
    registro_uid_a: str
    registro_uid_b: str
    similitud_jaccard: float


def detectar_casi_duplicados(
    textos_por_registro: dict[str, str], umbral_jaccard: float = 0.8
) -> list[ParCasiDuplicado]:
    lsh = MinHashLSH(threshold=umbral_jaccard, num_perm=N_PERMUTACIONES)
    minhashes = {}
    for registro_uid, texto in textos_por_registro.items():
        mh = calcular_minhash(texto)
        minhashes[registro_uid] = mh
        lsh.insert(registro_uid, mh)

    pares_vistos: set[tuple[str, str]] = set()
    pares: list[ParCasiDuplicado] = []
    for registro_uid, mh in minhashes.items():
        for candidato in lsh.query(mh):
            if candidato == registro_uid:
                continue
            clave = tuple(sorted((registro_uid, candidato)))
            if clave in pares_vistos:
                continue
            pares_vistos.add(clave)
            similitud = mh.jaccard(minhashes[candidato])
            pares.append(ParCasiDuplicado(clave[0], clave[1], round(similitud, 4)))
    return pares


def construir_grupos_duplicados(pares: list[ParCasiDuplicado]) -> dict[str, str]:
    """Componentes conexos de los pares detectados; el id de grupo es el menor `registro_uid`
    del componente (determinista, no depende del orden de llegada de los pares).
    """
    padre: dict[str, str] = {}

    def encontrar(nodo: str) -> str:
        while padre.get(nodo, nodo) != nodo:
            nodo = padre[nodo]
        return nodo

    def unir(a: str, b: str) -> None:
        raiz_a, raiz_b = encontrar(a), encontrar(b)
        if raiz_a != raiz_b:
            mayor, menor = max(raiz_a, raiz_b), min(raiz_a, raiz_b)
            padre[mayor] = menor

    for par in pares:
        padre.setdefault(par.registro_uid_a, par.registro_uid_a)
        padre.setdefault(par.registro_uid_b, par.registro_uid_b)
        unir(par.registro_uid_a, par.registro_uid_b)

    return {nodo: encontrar(nodo) for nodo in padre}
