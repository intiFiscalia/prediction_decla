"""Genera datos sintéticos para `tests/fixtures/` que imitan la estructura y los defectos de los
datos reales descritos en CLAUDE.md §4 (dos tablas CASOS/RELATOS, dos tablas sin coincidencia
perfecta, fechas M/D/AAAA, coordenadas sin separador decimal, mojibake cp1252→cp1251, IDs que un
lector de Numbers/Excel convierte a flotante, DELITO con artículo y cuantía pegados, etc.).

Este script **nunca** abre `data/raw/` ni `data/private/`. Todo nombre, cédula, teléfono, correo,
placa y relato es inventado; cualquier coincidencia con una persona o caso real es casualidad, no
una copia.

Uso:
    uv run python scripts/generar_fixtures.py
    uv run python scripts/generar_fixtures.py --seed 7 --n-noticias 200 --destino /tmp/fixtures
"""

from __future__ import annotations

import argparse
import hashlib
import random
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
import polars as pl

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
DESTINO_DEFECTO = RAIZ_PROYECTO / "tests" / "fixtures"
SEMILLA_DEFECTO = 20260131
FECHA_PROPIEDADES_FIJA = datetime(2026, 1, 1)

COLUMNAS_CASOS = [
    "CASO_NOTICIA",
    "CASO_ID",
    "DESP_ID",
    "TIPO_NOTICIA",
    "CASO_LEY",
    "LEY",
    "ESTADO",
    "ETAPA",
    "TIPO_DILIGENCIA",
    "FECHA_HECHO",
    "CASO_FECHA_DENUNCIA",
    "FECHA_CREACION",
    "CASO_FECHA_REG_NC",
    "FECHA_ASIGNACION",
    "CASO_FECHA_PRESCRIPCION",
    "FECHA_ULTIMA_ACTUACION",
    "FECHA_REGISTRO_ACTUACION",
    "ULTIMA_ACTUACION",
    "DELITO",
    "OTROS_DELITOS",
    "TITULO",
    "CAPITULO",
    "SECC_DESCRIPCION",
    "RUPTURA",
    "NO_CASOS_CONEXOS",
    "COMPETENCIA_DESPACHO",
    "DESP_CONOCIDO_CASO_TIT",
    "DESP_CONOCIDO_CASO_APOYO",
    "CASO_GRUPO_ESPECIALIZADO",
    "DEPARTAMENTO_HECHOS",
    "MUNICIPIO_HECHOS",
    "DEPARTAMENTO_UNIDAD",
    "MUNICIPIO_UNIDAD",
    "LAT_DIR_HECHOS",
    "LONG_DIR_HECHOS",
    "NUMERO_DOCUMENTO",
    "FISCAL_ASIGNADO_DESPACHO",
    "Eje temático APLICA",
    "DESPACHO",
    "PAIS_HECHOS",
]
assert len(COLUMNAS_CASOS) == 40, f"Se esperaban 40 columnas, hay {len(COLUMNAS_CASOS)}"

COLUMNAS_RELATOS = ["CASO_NOTICIA", "RELATO"]

# Territorios de ejemplo (códigos ilustrativos, no es una copia certificada de DIVIPOLA; dos
# municipios comparten nombre a propósito para poder probar la desambiguación por departamento).
TERRITORIOS = [
    {"cod_dpto": "11", "cod_mpio": "11001", "departamento": "BOGOTÁ, D.C.", "municipio": "BOGOTÁ, D.C.",
     "variantes_dpto": ["BOGOTÁ, D. C.", "Bogotá, D.C.", "BOGOTA DC", "Bogota D.C."], "lat": 4.6097, "long": -74.0817},
    {"cod_dpto": "50", "cod_mpio": "50001", "departamento": "META", "municipio": "VILLAVICENCIO",
     "variantes_dpto": ["Meta", "META "], "lat": 4.1420, "long": -73.6266},
    {"cod_dpto": "44", "cod_mpio": "44001", "departamento": "LA GUAJIRA", "municipio": "RIOHACHA",
     "variantes_dpto": ["La Guajira", "LA GUAJIRA "], "lat": 11.5444, "long": -72.9072},
    {"cod_dpto": "05", "cod_mpio": "05001", "departamento": "ANTIOQUIA", "municipio": "MEDELLÍN",
     "variantes_dpto": ["Antioquia", "ANTIOQUIA "], "lat": 6.2442, "long": -75.5812},
    {"cod_dpto": "76", "cod_mpio": "76001", "departamento": "VALLE DEL CAUCA", "municipio": "CALI",
     "variantes_dpto": ["Valle del Cauca"], "lat": 3.4516, "long": -76.5320},
    {"cod_dpto": "85", "cod_mpio": "85001", "departamento": "CASANARE", "municipio": "YOPAL",
     "variantes_dpto": ["Casanare"], "lat": 5.3378, "long": -72.3959},
    {"cod_dpto": "54", "cod_mpio": "54001", "departamento": "NORTE DE SANTANDER", "municipio": "CÚCUTA",
     "variantes_dpto": ["Norte de Santander"], "lat": 7.8939, "long": -72.5078},
    {"cod_dpto": "08", "cod_mpio": "08001", "departamento": "ATLÁNTICO", "municipio": "BARRANQUILLA",
     "variantes_dpto": ["Atlántico"], "lat": 10.9685, "long": -74.7813},
    {"cod_dpto": "05", "cod_mpio": "05042", "departamento": "ANTIOQUIA", "municipio": "SAN LUIS",
     "variantes_dpto": ["Antioquia"], "lat": 6.0433, "long": -74.9973},
    {"cod_dpto": "73", "cod_mpio": "73411", "departamento": "TOLIMA", "municipio": "SAN LUIS",
     "variantes_dpto": ["Tolima"], "lat": 4.0833, "long": -75.1333},
]

DELITOS = [
    {"nombre": "LAVADO DE ACTIVOS", "articulo": "323", "titulo": "TITULO X",
     "capitulo": "CAPITULO UNICO - LAVADO DE ACTIVOS"},
    {"nombre": "CONTRABANDO", "articulo": "319", "titulo": "TITULO XII",
     "capitulo": "CAPITULO VIII - CONTRABANDO"},
    {"nombre": "FAVORECIMIENTO DE CONTRABANDO", "articulo": "320", "titulo": "TITULO XII",
     "capitulo": "CAPITULO VIII - CONTRABANDO"},
    {"nombre": "ENRIQUECIMIENTO ILICITO DE PARTICULARES", "articulo": "327", "titulo": "TITULO X",
     "capitulo": "CAPITULO UNICO - LAVADO DE ACTIVOS"},
    {"nombre": "TESTAFERRATO", "articulo": "326", "titulo": "TITULO X",
     "capitulo": "CAPITULO UNICO - LAVADO DE ACTIVOS"},
    {"nombre": "CONCIERTO PARA DELINQUIR", "articulo": "340", "titulo": "TITULO XII",
     "capitulo": "CAPITULO I - CONCIERTO, ASOCIACION O PORTE DE ARMAS"},
]
CUANTIAS = [
    "CUANTIA INFERIOR A 100 SMLM",
    "CUANTIA SUPERIOR A 100 SMLM",
    "CUANTIA SUPERIOR A 150 SMLMV",
    "CUANTIA INDETERMINADA",
]

FENOMENOS: dict[str, dict[str, Any]] = {
    "contrabando_mercancias": {
        "nombre": "Contrabando de mercancías",
        "frases": [
            "Los investigadores hallaron mercancía de contrabando almacenada en una bodega en {municipio}.",
            "Se identificaron cajas de electrodomésticos sin declaración aduanera destinadas a comercializarse en {municipio}.",
            "El denunciante refiere que la mercancía ingresó al país sin el pago de los tributos aduaneros correspondientes.",
        ],
    },
    "contrabando_combustibles": {
        "nombre": "Contrabando de combustibles",
        "frases": [
            "Se localizaron pimpinas con combustible de contrabando transportadas desde la frontera hacia {municipio}.",
            "El operativo permitió incautar un vehículo acondicionado con tanques ocultos para transportar gasolina de contrabando.",
        ],
    },
    "subfacturacion": {
        "nombre": "Subfacturación y subpartidas arancelarias falsas",
        "frases": [
            "La DIAN detectó una declaración de importación con subpartida arancelaria falsa para reducir el pago de tributos.",
            "Se evidenció subfacturación sistemática en las facturas comerciales presentadas ante la autoridad aduanera.",
        ],
    },
    "fraccionamiento_consignaciones": {
        "nombre": "Fraccionamiento de consignaciones",
        "frases": [
            "Se detectaron múltiples consignaciones fraccionadas por montos inferiores al límite de reporte en diferentes entidades financieras.",
            "La investigación evidenció el uso de varias cuentas de terceros para fraccionar depósitos de dinero en efectivo.",
        ],
    },
    "empresas_fachada": {
        "nombre": "Empresas fachada",
        "frases": [
            "La sociedad constituida en {municipio} no registra actividad económica real y habría sido usada para justificar ingresos.",
            "Se identificó una empresa fachada sin empleados ni operaciones comerciales verificables.",
        ],
    },
    "testaferros": {
        "nombre": "Uso de testaferros",
        "frases": [
            "Los bienes se encuentran a nombre de un tercero que presuntamente actuaría como testaferro.",
            "Se evidenció que la propiedad fue transferida a una persona sin capacidad económica demostrada para adquirirla.",
        ],
    },
    "compra_inmuebles": {
        "nombre": "Compra de inmuebles con dinero de origen ilícito",
        "frases": [
            "Se adquirió un inmueble en {municipio} pagado en efectivo sin que el comprador justifique el origen de los recursos.",
            "La investigación identificó la compra de varios predios rurales en un periodo corto de tiempo.",
        ],
    },
    "compra_ganado": {
        "nombre": "Compra y venta de ganado",
        "frases": [
            "El investigado compraba cabezas de ganado en efectivo y las revendía en ferias de la región de {municipio}.",
            "Se reportó la adquisición irregular de semovientes sin los documentos de movilización exigidos.",
        ],
    },
    "mineria_ilegal_oro": {
        "nombre": "Minería ilegal de oro",
        "frases": [
            "Se identificó explotación de oro sin título minero en zona rural de {municipio}.",
            "El oro extraído de forma ilegal era comercializado a través de compraventas sin registro.",
        ],
    },
    "giros_casas_cambio": {
        "nombre": "Giros internacionales y casas de cambio",
        "frases": [
            "Se reportaron giros internacionales recibidos por distintas personas naturales sin relación aparente entre sí.",
            "La casa de cambio ubicada en {municipio} realizó operaciones de cambio de divisas sin reportar las de carácter inusual.",
        ],
    },
    "criptoactivos": {
        "nombre": "Uso de criptoactivos",
        "frases": [
            "Los recursos habrían sido convertidos a criptoactivos para dificultar su rastreo.",
            "Se identificaron transferencias de dinero hacia exchanges de criptomonedas sin justificación económica aparente.",
        ],
    },
    "captacion_ilegal": {
        "nombre": "Captación ilegal de dinero",
        "frases": [
            "La organización habría captado dinero del público ofreciendo rentabilidades superiores a las del mercado.",
            "Se identificó un esquema de captación masiva de recursos sin autorización de la autoridad financiera.",
        ],
    },
}

FRASES_NEGACION = [
    "No se halló evidencia física en el lugar de los hechos.",
    "No se encontraron elementos materiales probatorios adicionales en el lugar de los hechos.",
]
FRASES_HIPOTESIS = [
    "Presuntamente los recursos provendrían de actividades ilícitas relacionadas con el contrabando.",
    "Al parecer, la organización utilizaría testaferros para ocultar el origen de los bienes.",
    "Según el denunciante, los hechos habrían ocurrido de la forma antes descrita.",
]

NOMBRES_PILA = ["JUAN", "CARLOS", "MARIA", "LUZ", "JOSE", "ANDRES", "DIANA", "CAMILO", "SANDRA", "JORGE"]
APELLIDOS = ["GOMEZ", "PEREZ", "RODRIGUEZ", "MARTINEZ", "LOPEZ", "GARCIA", "DIAZ", "RAMIREZ", "TORRES", "VARGAS"]

MESES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
    "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]


# --------------------------------------------------------------------------------------
# Generadores de datos personales ficticios
# --------------------------------------------------------------------------------------


def generar_nombre(rng: random.Random) -> str:
    return f"{rng.choice(NOMBRES_PILA)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"


def generar_cedula(rng: random.Random, extranjera: bool = False) -> str:
    numero = rng.randint(10_000_000, 1_199_999_999)
    return f"C.E. {numero}" if extranjera else f"C.C. {numero}"


def generar_telefono(rng: random.Random) -> str:
    return f"3{rng.randint(0, 9)}{rng.randint(0, 9999999):07d}"


def generar_correo(rng: random.Random) -> str:
    return f"usuario{rng.randint(1000, 999999)}@correo-ficticio.example"


def generar_placa(rng: random.Random) -> str:
    letras = "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3))
    numeros = rng.randint(0, 999)
    return f"{letras}{numeros:03d}"


# --------------------------------------------------------------------------------------
# Fechas
# --------------------------------------------------------------------------------------


def sumar_anios(fecha: date, anios: int) -> date:
    try:
        return fecha.replace(year=fecha.year + anios)
    except ValueError:
        return fecha.replace(year=fecha.year + anios, day=28)


def fecha_a_texto_mdy(fecha: date) -> str:
    """Formato M/D/AAAA observado en la muestra real (sin ceros a la izquierda)."""
    return f"{fecha.month}/{fecha.day}/{fecha.year}"


def fecha_col_con_defecto(rng: random.Random, fecha: date, prob_invalida: float = 0.05) -> str:
    if rng.random() < prob_invalida:
        return rng.choice(["1/1/1900", "4/31/2026", "13/15/2026", "0/0/0000"])
    return fecha_a_texto_mdy(fecha)


def fecha_relato_variante(rng: random.Random, fecha: date) -> str:
    opcion = rng.choice(["num_dmy_slash", "texto_mes", "mes_slash_capital"])
    mes_nombre = MESES[fecha.month - 1]
    if opcion == "num_dmy_slash":
        return f"{fecha.day:02d}/{fecha.month:02d}/{fecha.year}"
    if opcion == "texto_mes":
        if mes_nombre == "AGOSTO" and rng.random() < 0.5:
            mes_nombre = "AGSOTO"
        return f"{fecha.day:02d} DE {mes_nombre} DEL {fecha.year}"
    return f"{fecha.day:02d}/{mes_nombre.capitalize()}/{fecha.year}"


def fecha_aleatoria(rng: random.Random, anio_min: int = 2021, anio_max: int = 2026) -> date:
    anio = rng.randint(anio_min, anio_max)
    mes = rng.randint(1, 12 if anio < 2026 else 10)
    dia = rng.randint(1, 28)
    return date(anio, mes, dia)


# --------------------------------------------------------------------------------------
# Identificadores
# --------------------------------------------------------------------------------------


def generar_caso_noticia(rng: random.Random, territorio: dict, anio: int, coherente: bool = True) -> str:
    if coherente:
        cod_entidad = "17"  # hipótesis de prueba, no un código DANE confirmado (CLAUDE.md §4.10)
        cod_unidad = f"{int(territorio['cod_mpio']) % 90000:05d}"
        consecutivo = f"{rng.randint(0, 99999):05d}"
        return f"{territorio['cod_mpio']}{cod_entidad}{cod_unidad}{anio}{consecutivo}"
    longitud = rng.choice([20, 21, 21, 21, 22])
    return "".join(str(rng.randint(0, 9)) for _ in range(longitud))


def renderizar_id(valor_limpio: str, modo: str) -> tuple[str, Any]:
    """Devuelve (texto_para_csv, valor_para_xlsx) según el defecto de tipo elegido."""
    if modo == "texto_limpio":
        return valor_limpio, valor_limpio
    if modo == "texto_punto0":
        return f"{valor_limpio}.0", f"{valor_limpio}.0"
    if len(valor_limpio) > 15:  # supera la precisión de float64 (~15-17 dígitos significativos)
        corrupto = format(float(valor_limpio), ".1f")
        return corrupto, float(corrupto)
    return f"{valor_limpio}.0", float(valor_limpio)


def elegir_modo_id(rng: random.Random) -> str:
    return rng.choices(["texto_limpio", "texto_punto0", "numero"], weights=[0.5, 0.25, 0.25])[0]


# --------------------------------------------------------------------------------------
# Coordenadas
# --------------------------------------------------------------------------------------


def generar_coordenada(rng: random.Random, territorio: dict) -> tuple[str, Any, str, Any, str]:
    """Devuelve (lat_csv, lat_xlsx, long_csv, long_xlsx, tipo_defecto)."""
    defecto = rng.choices(
        ["correcta", "sin_separador", "invertida", "fuera_colombia", "centroide", "vacia"],
        weights=[0.40, 0.20, 0.10, 0.10, 0.15, 0.05],
    )[0]

    if defecto == "vacia":
        return "", None, "", None, defecto

    if defecto == "centroide":
        lat, lon = territorio["lat"], territorio["long"]
    elif defecto == "fuera_colombia":
        lat, lon = rng.uniform(35.0, 55.0), rng.uniform(-10.0, 30.0)
    else:
        lat = territorio["lat"] + rng.uniform(-0.3, 0.3)
        lon = territorio["long"] + rng.uniform(-0.3, 0.3)
        lat, lon = round(lat, 3), round(lon, 3)

    if defecto == "invertida":
        lat, lon = lon, lat

    if defecto == "sin_separador":
        lat_txt = f"LAT {f'{lat:.3f}'.replace('.', '')}"
        lon_txt = f"LONG {f'{lon:.3f}'.replace('.', '')}"
        return lat_txt, lat_txt, lon_txt, lon_txt, defecto

    return str(lat), float(lat), str(lon), float(lon), defecto


# --------------------------------------------------------------------------------------
# Relatos
# --------------------------------------------------------------------------------------

TYPOS = {
    "APROXIMADAMENTE": "APROXIMADAMNETE",
    "TAMBIÉN": "TABIÉN",
    "RESPONSABLE": "RESPONSBLE",
}


def aplicar_typos(rng: random.Random, texto: str, prob: float = 0.4) -> str:
    for correcto, typo in TYPOS.items():
        if correcto in texto and rng.random() < prob:
            texto = texto.replace(correcto, typo)
    if rng.random() < 0.08 and "un ciudadano" in texto:
        texto = texto.replace("un ciudadano", "una ciudadana de sexo masculino", 1)
    return texto


def aplicar_mojibake(texto: str) -> str:
    """Reproduce el mojibake cp1252→cp1251 descrito en CLAUDE.md §4.15 (í→н, ó→у, ...)."""
    bytes_cp1252 = texto.encode("cp1252", errors="replace")
    return bytes_cp1252.decode("cp1251", errors="replace")


def _encabezado(rng: random.Random, estilo: str, territorio: dict) -> str:
    municipio = territorio["municipio"].title()
    departamento = territorio["departamento"].title()
    if estilo == "acta_policial_mayusculas":
        hora = f"{rng.randint(6, 23):02d}:{rng.choice(['00', '15', '30', '45'])}"
        return (
            f"SIENDO LAS {hora} HORAS DEL DIA DE HOY, EL SUSCRITO PATRULLERO ADSCRITO A LA "
            f"ESTACION DE POLICIA DE {municipio.upper()} DEJA CONSTANCIA DE LOS SIGUIENTES "
            f"HECHOS OCURRIDOS EN JURISDICCION DE {departamento.upper()}."
        )
    if estilo == "informe_fpj5_flagrancia":
        return (
            "INFORME EJECUTIVO FPJ-5. En cumplimiento de lo anterior, se deja constancia de la "
            f"captura en flagrancia ocurrida en {municipio}."
        )
    if estilo == "cooperacion_internacional":
        return (
            "En el marco de cooperación internacional, funcionarios de la DIAN en coordinación "
            f"con HSI, ICE y CBP intercambiaron información relacionada con una operación "
            f"detectada en {municipio}."
        )
    if estilo == "fuente_humana_anonima":
        return "Una fuente humana no identificada manifestó tener conocimiento de los siguientes hechos:"
    if estilo == "control_vial":
        return (
            f"En desarrollo de un control vial realizado en la vía que conduce a {municipio}, "
            "se procedió a la verificación documental del vehículo."
        )
    if estilo == "denuncia_uiaf":
        return (
            "La Unidad de Información y Análisis Financiero (UIAF) remitió reporte de operación "
            "sospechosa por transacciones inusuales en entidades financieras."
        )
    if estilo == "informe_dian":
        return (
            f"El suscrito funcionario adscrito a la DIAN, seccional {municipio}, refiere tener "
            "conocimiento de los siguientes hechos:"
        )
    return (  # denuncia_particular
        f"Siendo las {rng.randint(6, 20):02d} horas del día de hoy, comparece ante este despacho "
        "un ciudadano quien refiere tener conocimiento de los siguientes hechos:"
    )


ESTILOS = [
    "acta_policial_mayusculas",
    "informe_fpj5_flagrancia",
    "cooperacion_internacional",
    "fuente_humana_anonima",
    "control_vial",
    "denuncia_uiaf",
    "informe_dian",
    "denuncia_particular",
]


def construir_relato(
    rng: random.Random, estilo: str, fenomeno_id: str, territorio: dict, fecha_hecho: date
) -> tuple[str, str | None]:
    fenomeno = FENOMENOS[fenomeno_id]
    fenomeno_secundario_id = rng.choice(list(FENOMENOS)) if rng.random() < 0.25 else None

    oraciones = [_encabezado(rng, estilo, territorio)]
    municipio = territorio["municipio"].title()
    for frase in fenomeno["frases"]:
        oraciones.append(frase.format(municipio=municipio))
    if fenomeno_secundario_id:
        for frase in FENOMENOS[fenomeno_secundario_id]["frases"][:1]:
            oraciones.append(frase.format(municipio=municipio))

    nombre = generar_nombre(rng)
    cedula = generar_cedula(rng, extranjera=rng.random() < 0.1)
    oraciones.append(
        f"Como presunto responsable se señala a {nombre}, identificado con {cedula}, "
        f"quien registra el número de contacto {generar_telefono(rng)}, el correo "
        f"{generar_correo(rng)} y el vehículo de placas {generar_placa(rng)}."
    )
    if rng.random() < 0.4:
        oraciones.append(rng.choice(FRASES_NEGACION))
    if rng.random() < 0.4:
        oraciones.append(rng.choice(FRASES_HIPOTESIS))
    oraciones.append(
        f"Los hechos habrían ocurrido aproximadamente el {fecha_relato_variante(rng, fecha_hecho)}."
    )

    objetivo_palabras = rng.randint(60, 2000)
    texto_partes: list[str] = []
    while sum(len(p.split()) for p in texto_partes) < objetivo_palabras:
        texto_partes.append(rng.choice(oraciones))

    texto = " ".join(texto_partes)
    texto = aplicar_typos(rng, texto)
    if estilo == "acta_policial_mayusculas":
        texto = texto.upper()
    return texto, fenomeno_secundario_id


@dataclass
class FilaLogicaCaso:
    caso_noticia: str
    caso_id: str
    desp_id: str
    numero_documento: str
    territorio: dict
    fecha_hecho: date
    delito: dict
    cuantia: str


def construir_delito_texto(delito: dict, cuantia: str) -> str:
    return f"{delito['nombre']} ART. {delito['articulo']} C.P.{cuantia}"


def construir_fila_caso(rng: random.Random, logica: FilaLogicaCaso) -> dict[str, dict[str, Any]]:
    """Devuelve {columna: {"csv": valor, "xlsx": valor}} para una fila completa de CASOS."""
    territorio = logica.territorio
    fecha_denuncia = logica.fecha_hecho
    fecha_creacion = logica.fecha_hecho
    fecha_asignacion = logica.fecha_hecho
    prescripcion = sumar_anios(logica.fecha_hecho, 20)
    if rng.random() < 0.1:
        prescripcion = sumar_anios(logica.fecha_hecho, 10)  # excepción deliberada a verificar

    lat_csv, lat_xlsx, long_csv, long_xlsx, _ = generar_coordenada(rng, territorio)

    # Corromper CASO_NOTICIA aquí (pero no en RELATOS) reduce a propósito la tasa de
    # coincidencia textual entre las dos tablas: es la hipótesis más plausible para el
    # hallazgo de "0 coincidencias" de CLAUDE.md §4.3, y obliga a que la limpieza de IDs
    # ocurra ANTES de intentar el cruce CASOS↔RELATOS, no después.
    caso_noticia_csv, caso_noticia_xlsx = renderizar_id(logica.caso_noticia, elegir_modo_id(rng))
    caso_id_csv, caso_id_xlsx = renderizar_id(logica.caso_id, elegir_modo_id(rng))
    desp_id_csv, desp_id_xlsx = renderizar_id(logica.desp_id, elegir_modo_id(rng))
    doc_csv, doc_xlsx = renderizar_id(logica.numero_documento, elegir_modo_id(rng))

    departamento_txt = rng.choice([territorio["departamento"], *territorio["variantes_dpto"]])
    municipio_txt = rng.choice([territorio["municipio"], territorio["municipio"].title()])
    etapa_txt = rng.choices(["INDAGACIÓN", "INVESTIGACIÓN", "JUICIO"], weights=[0.7, 0.2, 0.1])[0]
    competencia_txt = rng.choices(
        ["FISCALÍA ESPECIALIZADA DECLA", "FISCALÍA SECCIONAL", "FISCALÍA LOCAL"],
        weights=[0.7, 0.2, 0.1],
    )[0]
    eje_tematico_txt = rng.choices(
        ["por establecer", "0", "LAVADO DE ACTIVOS"], weights=[0.5, 0.3, 0.2]
    )[0]
    pais_txt = rng.choices(["COLOMBIA", "ESTADOS UNIDOS", "PANAMÁ"], weights=[0.9, 0.06, 0.04])[0]

    def ambos(valor: Any) -> dict[str, Any]:
        return {"csv": valor, "xlsx": valor}

    return {
        "CASO_NOTICIA": {"csv": caso_noticia_csv, "xlsx": caso_noticia_xlsx},
        "CASO_ID": {"csv": caso_id_csv, "xlsx": caso_id_xlsx},
        "DESP_ID": {"csv": desp_id_csv, "xlsx": desp_id_xlsx},
        "TIPO_NOTICIA": ambos(etapa_txt),
        "CASO_LEY": ambos(rng.choices(["LEY 906", "LEY 600"], weights=[0.85, 0.15])[0]),
        "LEY": ambos("906"),
        "ESTADO": ambos(rng.choices(["ACTIVO", "INACTIVO", "ARCHIVADO"], weights=[0.8, 0.1, 0.1])[0]),
        "ETAPA": ambos(etapa_txt),
        "TIPO_DILIGENCIA": ambos(rng.choice(["DENUNCIA", "INFORME DE POLICIA JUDICIAL", "QUERELLA"])),
        "FECHA_HECHO": ambos(fecha_col_con_defecto(rng, logica.fecha_hecho)),
        "CASO_FECHA_DENUNCIA": ambos(fecha_col_con_defecto(rng, fecha_denuncia)),
        "FECHA_CREACION": ambos(fecha_col_con_defecto(rng, fecha_creacion)),
        "CASO_FECHA_REG_NC": ambos(fecha_col_con_defecto(rng, fecha_creacion)),
        "FECHA_ASIGNACION": ambos(fecha_col_con_defecto(rng, fecha_asignacion)),
        "CASO_FECHA_PRESCRIPCION": ambos(
            fecha_col_con_defecto(rng, prescripcion, prob_invalida=0.0)
        ),
        "FECHA_ULTIMA_ACTUACION": ambos(fecha_col_con_defecto(rng, fecha_asignacion)),
        "FECHA_REGISTRO_ACTUACION": ambos(fecha_col_con_defecto(rng, fecha_asignacion)),
        "ULTIMA_ACTUACION": ambos(
            rng.choice(["ASIGNACION", "SOLICITUD DE INFORMACION", "ORDEN A POLICIA JUDICIAL"])
        ),
        "DELITO": ambos(construir_delito_texto(logica.delito, logica.cuantia)),
        "OTROS_DELITOS": ambos(rng.choice(DELITOS)["nombre"] if rng.random() < 0.05 else None),
        "TITULO": ambos(logica.delito["titulo"]),
        "CAPITULO": ambos(logica.delito["capitulo"]),
        "SECC_DESCRIPCION": ambos(
            rng.choices(["DECLA", "SECCIONAL DELITOS INFORMATICOS"], weights=[0.8, 0.2])[0]
        ),
        "RUPTURA": ambos(rng.choice(["SI", "PARCIAL"]) if rng.random() < 0.05 else None),
        "NO_CASOS_CONEXOS": ambos(str(rng.randint(0, 5)) if rng.random() < 0.3 else None),
        "COMPETENCIA_DESPACHO": ambos(competencia_txt),
        "DESP_CONOCIDO_CASO_TIT": ambos(rng.choice(["SI", "NO"])),
        "DESP_CONOCIDO_CASO_APOYO": ambos(rng.choice(["SI", "NO"]) if rng.random() < 0.2 else None),
        "CASO_GRUPO_ESPECIALIZADO": ambos(
            rng.choice(["GRUPO LAVADO DE ACTIVOS"]) if rng.random() < 0.05 else None
        ),
        "DEPARTAMENTO_HECHOS": ambos(departamento_txt),
        "MUNICIPIO_HECHOS": ambos(municipio_txt),
        "DEPARTAMENTO_UNIDAD": ambos(departamento_txt),
        "MUNICIPIO_UNIDAD": ambos(municipio_txt),
        "LAT_DIR_HECHOS": {"csv": lat_csv, "xlsx": lat_xlsx},
        "LONG_DIR_HECHOS": {"csv": long_csv, "xlsx": long_xlsx},
        "NUMERO_DOCUMENTO": {"csv": doc_csv, "xlsx": doc_xlsx},
        "FISCAL_ASIGNADO_DESPACHO": ambos(generar_nombre(rng)),
        "Eje temático APLICA": ambos(eje_tematico_txt),
        "DESPACHO": ambos(f"FISCALÍA {rng.randint(1, 40)} DECLA {territorio['municipio'].title()}"),
        "PAIS_HECHOS": ambos(pais_txt),
    }


# --------------------------------------------------------------------------------------
# Construcción de las tablas completas
# --------------------------------------------------------------------------------------


def construir_casos_y_verdad_relatos(
    rng: random.Random, n_noticias: int
) -> tuple[list[dict[str, dict[str, Any]]], list[FilaLogicaCaso]]:
    filas: list[dict[str, dict[str, Any]]] = []
    logicas: list[FilaLogicaCaso] = []

    for i in range(n_noticias):
        territorio = rng.choice(TERRITORIOS)
        fecha_hecho = fecha_aleatoria(rng)
        anio_notic = fecha_hecho.year
        coherente = rng.random() < 0.85
        caso_noticia = generar_caso_noticia(rng, territorio, anio_notic, coherente=coherente)
        logica = FilaLogicaCaso(
            caso_noticia=caso_noticia,
            caso_id=str(100_000 + i),
            desp_id=str(1000 + (i % 400)),
            numero_documento=str(rng.randint(1_000_000, 1_199_999_999)),
            territorio=territorio,
            fecha_hecho=fecha_hecho,
            delito=rng.choice(DELITOS),
            cuantia=rng.choice(CUANTIAS),
        )
        logicas.append(logica)
        filas.append(construir_fila_caso(rng, logica))

        # Multidelito: ~5% de las noticias reciben una fila adicional con otro delito.
        if rng.random() < 0.05:
            logica_multi = FilaLogicaCaso(
                caso_noticia=caso_noticia,
                caso_id=logica.caso_id,
                desp_id=logica.desp_id,
                numero_documento=logica.numero_documento,
                territorio=territorio,
                fecha_hecho=fecha_hecho,
                delito=rng.choice([d for d in DELITOS if d != logica.delito]),
                cuantia=rng.choice(CUANTIAS),
            )
            filas.append(construir_fila_caso(rng, logica_multi))

        # Duplicado exacto: ~3% de las filas se repiten tal cual.
        if rng.random() < 0.03:
            filas.append(filas[-1])

    # Filas totalmente vacías intercaladas (CLAUDE.md §4.2).
    n_vacias = max(1, round(len(filas) * 0.07))
    posiciones = sorted(rng.sample(range(len(filas) + n_vacias), n_vacias))
    fila_vacia = {col: {"csv": None, "xlsx": None} for col in COLUMNAS_CASOS}
    for pos in posiciones:
        filas.insert(pos, dict(fila_vacia))

    rng.shuffle(filas)  # el orden de llegada no debe asumirse significativo
    return filas, logicas


def construir_relatos_y_verdad(
    rng: random.Random, logicas: list[FilaLogicaCaso]
) -> tuple[list[dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    filas: list[dict[str, dict[str, Any]]] = []
    verdad: list[dict[str, Any]] = []
    caso_noticias_existentes = {logica.caso_noticia for logica in logicas}
    contador = 0

    for logica in logicas:
        n_relatos = rng.choices([0, 1, 2], weights=[0.25, 0.65, 0.10])[0]
        for _ in range(n_relatos):
            estilo = rng.choice(ESTILOS)
            fenomeno_id = rng.choice(list(FENOMENOS))
            texto, fenomeno_secundario = construir_relato(
                rng, estilo, fenomeno_id, logica.territorio, logica.fecha_hecho
            )
            aplica_mojibake = rng.random() < 0.70
            texto_final = aplicar_mojibake(texto) if aplica_mojibake else texto
            contador += 1
            relato_id = f"SINT-{contador:05d}"

            filas.append(
                {
                    "CASO_NOTICIA": {"csv": logica.caso_noticia, "xlsx": logica.caso_noticia},
                    "RELATO": {"csv": texto_final, "xlsx": texto_final},
                }
            )
            verdad.append(
                {
                    "relato_id": relato_id,
                    "caso_noticia": logica.caso_noticia,
                    "estilo": estilo,
                    "fenomeno_plantado": fenomeno_id,
                    "fenomeno_secundario_plantado": fenomeno_secundario,
                    "mojibake_aplicado": aplica_mojibake,
                    "longitud_palabras": len(texto.split()),
                    "texto_antes_de_mojibake": texto,
                }
            )

    # Relatos huérfanos: CASO_NOTICIA que no existe en CASOS (CLAUDE.md §4.3).
    n_huerfanos = max(1, round(len(filas) * 0.10))
    for _ in range(n_huerfanos):
        territorio = rng.choice(TERRITORIOS)
        fecha_hecho = fecha_aleatoria(rng)
        while True:
            caso_noticia_huerfano = generar_caso_noticia(rng, territorio, fecha_hecho.year, coherente=True)
            if caso_noticia_huerfano not in caso_noticias_existentes:
                break
        estilo = rng.choice(ESTILOS)
        fenomeno_id = rng.choice(list(FENOMENOS))
        texto, fenomeno_secundario = construir_relato(rng, estilo, fenomeno_id, territorio, fecha_hecho)
        aplica_mojibake = rng.random() < 0.70
        texto_final = aplicar_mojibake(texto) if aplica_mojibake else texto
        contador += 1
        filas.append(
            {
                "CASO_NOTICIA": {"csv": caso_noticia_huerfano, "xlsx": caso_noticia_huerfano},
                "RELATO": {"csv": texto_final, "xlsx": texto_final},
            }
        )
        verdad.append(
            {
                "relato_id": f"SINT-{contador:05d}",
                "caso_noticia": caso_noticia_huerfano,
                "estilo": estilo,
                "fenomeno_plantado": fenomeno_id,
                "fenomeno_secundario_plantado": fenomeno_secundario,
                "mojibake_aplicado": aplica_mojibake,
                "longitud_palabras": len(texto.split()),
                "texto_antes_de_mojibake": texto,
            }
        )

    # Filas totalmente vacías intercaladas.
    n_vacias = max(1, round(len(filas) * 0.05))
    fila_vacia = {col: {"csv": None, "xlsx": None} for col in COLUMNAS_RELATOS}
    for _ in range(n_vacias):
        pos = rng.randint(0, len(filas))
        filas.insert(pos, dict(fila_vacia))

    rng.shuffle(filas)
    return filas, verdad


# --------------------------------------------------------------------------------------
# Escritura de archivos
# --------------------------------------------------------------------------------------


def escribir_csv(filas: list[dict[str, dict[str, Any]]], columnas: list[str], ruta: Path) -> None:
    datos = {
        columna: [fila[columna]["csv"] for fila in filas] for columna in columnas
    }
    df = pl.DataFrame(datos, schema={c: pl.Utf8 for c in columnas})
    df.write_csv(ruta)


_ZIP_FECHA_FIJA = (2026, 1, 1, 0, 0, 0)
_PATRON_MODIFIED = re.compile(rb"<dcterms:modified[^>]*>.*?</dcterms:modified>")
_MODIFIED_FIJO = b'<dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:modified>'


def _hacer_xlsx_deterministico(ruta: Path) -> None:
    """openpyxl estampa `modified` con la hora real al guardar (writer/excel.py) y el zip
    resultante lleva timestamps por archivo con resolución de segundos: sin esto, el mismo
    contenido produce un `.xlsx` distinto en cada ejecución. Se reescribe el zip con fechas
    fijas para que la salida sea reproducible byte a byte.
    """
    with zipfile.ZipFile(ruta, "r") as zip_entrada:
        entradas = [(info, zip_entrada.read(info.filename)) for info in zip_entrada.infolist()]

    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as zip_salida:
        for info, contenido in entradas:
            if info.filename == "docProps/core.xml":
                contenido = _PATRON_MODIFIED.sub(_MODIFIED_FIJO, contenido)
            nueva_info = zipfile.ZipInfo(info.filename, date_time=_ZIP_FECHA_FIJA)
            nueva_info.compress_type = zipfile.ZIP_DEFLATED
            zip_salida.writestr(nueva_info, contenido)


def escribir_xlsx(filas: list[dict[str, dict[str, Any]]], columnas: list[str], ruta: Path) -> None:
    libro = openpyxl.Workbook()
    libro.properties.creator = "decla-fixtures"
    libro.properties.lastModifiedBy = "decla-fixtures"
    libro.properties.created = FECHA_PROPIEDADES_FIJA
    libro.properties.modified = FECHA_PROPIEDADES_FIJA
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(columnas)
    for fila in filas:
        hoja.append([fila[columna]["xlsx"] for columna in columnas])
    libro.save(ruta)
    _hacer_xlsx_deterministico(ruta)


def hash_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------------------


def generar(seed: int, n_noticias: int, destino: Path) -> dict[str, str]:
    destino.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    filas_casos, logicas = construir_casos_y_verdad_relatos(rng, n_noticias)
    filas_relatos, verdad = construir_relatos_y_verdad(rng, logicas)

    rutas = {
        "casos_csv": destino / "casos_sinteticos.csv",
        "casos_xlsx": destino / "casos_sinteticos.xlsx",
        "relatos_csv": destino / "relatos_sinteticos.csv",
        "relatos_xlsx": destino / "relatos_sinteticos.xlsx",
        "verdad": destino / "verdad.parquet",
    }

    escribir_csv(filas_casos, COLUMNAS_CASOS, rutas["casos_csv"])
    escribir_xlsx(filas_casos, COLUMNAS_CASOS, rutas["casos_xlsx"])
    escribir_csv(filas_relatos, COLUMNAS_RELATOS, rutas["relatos_csv"])
    escribir_xlsx(filas_relatos, COLUMNAS_RELATOS, rutas["relatos_xlsx"])
    pl.DataFrame(verdad).write_parquet(rutas["verdad"])

    return {nombre: hash_archivo(ruta) for nombre, ruta in rutas.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEMILLA_DEFECTO)
    parser.add_argument("--n-noticias", type=int, default=400)
    parser.add_argument("--destino", type=Path, default=DESTINO_DEFECTO)
    args = parser.parse_args(argv)

    hashes = generar(args.seed, args.n_noticias, args.destino)

    print("Fixtures generados en", args.destino)
    for nombre, digest in hashes.items():
        print(f"  {nombre}: sha256:{digest}")
    print(
        "Nota: no se genera '.numbers' porque numbers-parser es de solo lectura; "
        "la ingesta debe soportar igual csv/xlsx (ver docs/decisiones/0001-pila-tecnologica.md)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
