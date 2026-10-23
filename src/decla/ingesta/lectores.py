"""Lectura de fuentes SPOA en `.csv`, `.xlsx` y `.numbers` (CLAUDE.md §4.1, plan_trabajo.md Fase 1).

Todo se lee **como texto** y sin transformar: si una celda de identificador llega como `"123.0"`
(el lector original la convirtió a flotante), este módulo la conserva tal cual para que
`decla.calidad` pueda medir el defecto. La limpieza y normalización son de I1, no de aquí.

Las filas totalmente vacías se cuentan y se excluyen; se conserva el número de fila original
(1 = encabezado, 2 = primera fila de datos) para poder referenciarlas en el informe de calidad.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TablaLeida:
    nombre: str
    columnas: list[str]
    filas: list[dict[str, str | None]]
    fila_origen: list[int]
    n_filas_total: int
    n_filas_vacias: int
    advertencias: list[str] = field(default_factory=list)

    @property
    def n_filas_datos(self) -> int:
        return len(self.filas)


def _valor_a_texto(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor if valor != "" else None
    return str(valor)


def _ensamblar(filas_crudas: list[list[Any]], nombre: str, advertencias: list[str]) -> TablaLeida:
    if not filas_crudas:
        return TablaLeida(
            nombre=nombre,
            columnas=[],
            filas=[],
            fila_origen=[],
            n_filas_total=0,
            n_filas_vacias=0,
            advertencias=[*advertencias, "archivo o tabla sin filas"],
        )

    columnas = [(_valor_a_texto(c) or "").strip() for c in filas_crudas[0]]
    filas: list[dict[str, str | None]] = []
    fila_origen: list[int] = []
    n_vacias = 0

    for idx, fila_cruda in enumerate(filas_crudas[1:], start=2):
        valores = [_valor_a_texto(v) for v in fila_cruda]
        if len(valores) < len(columnas):
            valores = valores + [None] * (len(columnas) - len(valores))
        elif len(valores) > len(columnas):
            advertencias.append(
                f"fila {idx}: {len(valores)} celdas para {len(columnas)} columnas; "
                "se truncan las sobrantes"
            )
            valores = valores[: len(columnas)]

        fila_dict = dict(zip(columnas, valores, strict=True))
        if all(v is None for v in fila_dict.values()):
            n_vacias += 1
            continue
        filas.append(fila_dict)
        fila_origen.append(idx)

    if n_vacias:
        advertencias.append(f"{n_vacias} filas completamente vacías excluidas")

    return TablaLeida(
        nombre=nombre,
        columnas=columnas,
        filas=filas,
        fila_origen=fila_origen,
        n_filas_total=len(filas_crudas) - 1,
        n_filas_vacias=n_vacias,
        advertencias=advertencias,
    )


def _detectar_codificacion(contenido: bytes) -> str:
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            contenido.decode(codificacion)
            return codificacion
        except UnicodeDecodeError:
            continue
    return "latin-1"  # latin-1 nunca falla: mapea todo byte 0-255, es el último recurso


def _detectar_separador(texto: str) -> str:
    muestra = "\n".join(texto.splitlines()[:5])
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def leer_csv(ruta: Path, nombre: str | None = None) -> TablaLeida:
    contenido = ruta.read_bytes()
    codificacion = _detectar_codificacion(contenido)
    texto = contenido.decode(codificacion)
    separador = _detectar_separador(texto)
    advertencias = [
        f"codificación detectada: {codificacion}",
        f"separador detectado: {separador!r}",
    ]

    filas_crudas = list(csv.reader(io.StringIO(texto), delimiter=separador))
    return _ensamblar(filas_crudas, nombre or ruta.stem, advertencias)


def leer_xlsx(ruta: Path, hoja: str | None = None, nombre: str | None = None) -> TablaLeida:
    from python_calamine import CalamineWorkbook

    libro = CalamineWorkbook.from_path(str(ruta))
    nombre_hoja = hoja if hoja in libro.sheet_names else libro.sheet_names[0]
    filas_crudas = libro.get_sheet_by_name(nombre_hoja).to_python(skip_empty_area=False)
    advertencias = [f"hoja leída: {nombre_hoja}"]
    return _ensamblar(filas_crudas, nombre or ruta.stem, advertencias)


def leer_numbers(
    ruta: Path, hoja: str | None = None, tabla: str | None = None, nombre: str | None = None
) -> TablaLeida:
    import numbers_parser

    documento = numbers_parser.Document(str(ruta))
    hojas = documento.sheets
    hoja_obj = next((h for h in hojas if h.name == hoja), hojas[0])
    tablas = hoja_obj.tables
    tabla_obj = next((t for t in tablas if t.name == tabla), tablas[0])

    filas_crudas = tabla_obj.rows(values_only=True)
    advertencias = [f"hoja leída: {hoja_obj.name}", f"tabla leída: {tabla_obj.name}"]
    return _ensamblar(filas_crudas, nombre or ruta.stem, advertencias)


LECTORES_POR_EXTENSION: dict[str, Callable[..., TablaLeida]] = {
    ".csv": leer_csv,
    ".xlsx": leer_xlsx,
    ".numbers": leer_numbers,
}


def leer_tabla(ruta: Path, **kwargs: Any) -> TablaLeida:
    extension = ruta.suffix.lower()
    lector = LECTORES_POR_EXTENSION.get(extension)
    if lector is None:
        raise ValueError(
            f"Extensión no soportada: {extension!r} ({ruta.name}). "
            f"Se admite: {sorted(LECTORES_POR_EXTENSION)}"
        )
    return lector(ruta, **kwargs)
