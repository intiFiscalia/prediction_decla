# Diccionario de datos — fuente SPOA (CASOS + RELATOS)

Fuente de verdad del esquema: `config/esquema_fuente.yaml` (el validador `decla.ingesta.esquema`
se ejecuta contra él). Este diccionario añade el hallazgo conocido de cada columna; cuando
`make diagnostico` corra sobre datos reales, se actualiza con las cifras reales (marcadas abajo
como "pendiente de datos reales").

Columnas nuevas frente al inventario original de 28 del plan (CLAUDE.md §4.4): RUPTURA,
TIPO_NOTICIA, CASO_LEY, LEY, SECC_DESCRIPCION, CAPITULO, FECHA_ULTIMA_ACTUACION,
FECHA_REGISTRO_ACTUACION, ULTIMA_ACTUACION, OTROS_DELITOS, DESP_CONOCIDO_CASO_TIT,
DESP_CONOCIDO_CASO_APOYO, CASO_GRUPO_ESPECIALIZADO, "Eje temático APLICA".

## CASOS

| Columna | Tipo esperado | Obligatoria | Hallazgo conocido |
| --- | --- | --- | --- |
| CASO_NOTICIA | identificador | sí | 21 dígitos (hipótesis: cod_mpio(5)+entidad(2)+unidad(5)+año(4)+consecutivo(5), CLAUDE.md §4.10); llave de unión con RELATOS, con corrupción de tipo (".0"/flotante) que reduce la coincidencia textual |
| CASO_ID | identificador | sí | el lector de Numbers lo convierte a flotante (CLAUDE.md §4.9); forzar texto, quitar ".0" |
| DESP_ID | identificador | sí | mismo defecto que CASO_ID |
| TIPO_NOTICIA | categórico | no | — |
| CASO_LEY | categórico | no | — |
| LEY | categórico | no | — |
| ESTADO | categórico | sí | en la muestra, todo "ACTIVO" (CLAUDE.md §4.19); verificar variedad real |
| ETAPA | categórico | sí | en la muestra, todo "INDAGACIÓN"; verificar variedad real |
| TIPO_DILIGENCIA | categórico | no | — |
| FECHA_HECHO | fecha | sí | texto M/D/AAAA, formato a detectar por columna, no asumir (CLAUDE.md §4.11) |
| CASO_FECHA_DENUNCIA | fecha | no | orden lógico esperado: FECHA_HECHO ≤ esta |
| FECHA_CREACION | fecha | sí | usada como fecha de referencia provisional del perfil temporal de I0 |
| CASO_FECHA_REG_NC | fecha | no | — |
| FECHA_ASIGNACION | fecha | no | — |
| CASO_FECHA_PRESCRIPCION | fecha | no | en la muestra = FECHA_HECHO + 20 años; verificar en todo el dataset (CLAUDE.md §4.13) |
| FECHA_ULTIMA_ACTUACION | fecha | no | — |
| FECHA_REGISTRO_ACTUACION | fecha | no | — |
| ULTIMA_ACTUACION | categórico | no | — |
| DELITO | texto estructurado | sí | mezcla artículo y cuantía (CLAUDE.md §4.18); se separa por regex en `decla.calidad.categoricas.parsear_delito` |
| OTROS_DELITOS | texto estructurado | no | vacía en la muestra (CLAUDE.md §4.7) |
| TITULO | categórico | no | jerarquía del Código Penal junto con CAPITULO |
| CAPITULO | categórico | no | — |
| SECC_DESCRIPCION | categórico | no | en la muestra, todo "DECLA" |
| RUPTURA | categórico | no | vacía en la muestra (CLAUDE.md §4.7) |
| NO_CASOS_CONEXOS | numérico | no | — |
| COMPETENCIA_DESPACHO | categórico | no | — |
| DESP_CONOCIDO_CASO_TIT | categórico | no | — |
| DESP_CONOCIDO_CASO_APOYO | categórico | no | — |
| CASO_GRUPO_ESPECIALIZADO | categórico | no | casi vacía en la muestra (CLAUDE.md §4.7) |
| DEPARTAMENTO_HECHOS | territorio | sí | variantes de mayúsculas/tildes/"D.C." (CLAUDE.md §4.16) |
| MUNICIPIO_HECHOS | territorio | sí | mismo defecto; homónimos en distintos departamentos |
| DEPARTAMENTO_UNIDAD | territorio | no | geografía distinta de HECHOS: analizar por separado (plan_trabajo.md §8.2) |
| MUNICIPIO_UNIDAD | territorio | no | — |
| LAT_DIR_HECHOS | coordenada | no | sin separador decimal, invertida, fuera de caja (CLAUDE.md §4.17) |
| LONG_DIR_HECHOS | coordenada | no | mismo defecto; tipos mixtos en la misma columna |
| NUMERO_DOCUMENTO | identificador sensible | no | se seudonimiza en plata (I1); mismo defecto de flotante que CASO_ID |
| FISCAL_ASIGNADO_DESPACHO | nombre de servidor | no | dato personal de servidor público; seudonimizar |
| Eje temático APLICA | categórico | no | valores "por establecer" y "0"; **no es alias de EJE_TEMATICO** (CLAUDE.md §4.5, pregunta abierta) |
| DESPACHO | categórico | no | — |
| PAIS_HECHOS | categórico | no | — |
| EJE_TEMATICO (heredada) | categórico | no | del inventario original; si aparece en datos reales, reportar, no fusionar con "Eje temático APLICA" |

## RELATOS

| Columna | Tipo esperado | Obligatoria | Hallazgo conocido |
| --- | --- | --- | --- |
| CASO_NOTICIA | identificador | sí | llave de unión con CASOS; en la muestra real, 0 coincidencias (CLAUDE.md §4.3) |
| RELATO | texto libre | sí | 492–12.056 caracteres; mojibake cp1252→cp1251 sistemático; datos personales abundantes (CLAUDE.md §4.20–24) |

## Pendiente de datos reales

- Variedad real de ESTADO, ETAPA, SECC_DESCRIPCION, LEY, CASO_LEY, TIPO_NOTICIA (en la muestra
  son casi constantes).
- % real de columnas faltantes por año y departamento.
- Confirmación o refutación de la hipótesis de estructura de CASO_NOTICIA a escala completa.
- Periodo real cubierto y si permite pronósticos (≥ 36 meses, plan_trabajo.md §8.4).
