# Cierre de I0 — Diagnóstico de datos y arquitectura

- **Fecha:** 2026-10-23
- **Corridas de `make diagnostico` sobre datos reales:** dos (978 filas de CASOS/RELATOS cada vez).

## Entregables

- `config/esquema_fuente.yaml`, `config/reglas_fechas.yaml`: contratos versionados.
- `src/decla/ingesta/{lectores,esquema}.py` y `src/decla/calidad/{cardinalidad,fechas,territorio,
  coordenadas,categoricas,relatos,temporal,muestra,diagnostico}.py`: 95 pruebas unitarias/integración,
  todas contra `tests/fixtures/` (nunca contra datos reales).
- `reports/agregados/diagnostico/`: `informe.md`, ~25 CSVs agregados (supresión `<5`), 3 PNG.
- `data/private/diagnostico/muestra_lectura/`: muestra estratificada de relatos para lectura humana
  (nunca abierta por Claude Code).
- `docs/fichas/diccionario_datos.md`.
- ADRs: 0001 (pila tecnológica), 0002 (unidad de análisis, **aceptada**), 0003–0007 (almacenamiento,
  granularidad temporal, embeddings, orquestación, respaldo — todas con decisión provisional o
  explícitamente pendiente), 0008 (alcance temático y prescripción, **aceptada**).

## Métricas clave del dataset real (978 filas)

| Métrica | Valor |
| --- | --- |
| Grano | 1 fila = 1 noticia criminal (978 = 978 = 978, 0 duplicados) |
| Unión CASOS↔RELATOS | 100 % de coincidencia en ambos sentidos, 0 huérfanos |
| `CASO_NOTICIA` 21 dígitos | 100 %; 99,8 % con año embebido correcto; prefijo DANE **no verificado** (falta DIVIPOLA) |
| Regla "prescripción = hecho + 20 años" | 19,1 % de cumplimiento exacto — **no se usa como regla de validación** |
| Mojibake cirílico | 0 relatos |
| Coordenadas | 95,4 % correctas, 4,5 % vacías, 0,1 % reparadas, 0 % invertidas/fuera de caja |
| Periodo cubierto | 2026-01 a 2026-10 (10 meses) |
| `DELITO` parseable | 96,2 % (941/978) |
| Alcance temático (`SECC_DESCRIPCION`) | 64 % Delitos Fiscales, 35 % Lavado de Activos, 1 % otros |

## Decisiones de la compuerta (aprobadas por la persona, 2026-10-23)

1. **Unidad de análisis:** una fila = una noticia criminal (ADR 0002).
2. **Alcance:** limitado a "Dirección Especializada contra el Lavado de Activos" (347 de 978
   filas observadas); Delitos Fiscales queda fuera. El filtro se aplica en plata/entidades de I1,
   nunca en bronce (ADR 0008).
3. **Prescripción:** tratamiento informativo, no normativo; no se valida contra "hecho + 20 años"
   (ADR 0008).
4. **`eje tmeatico APLICA`:** contrato corregido para reconocer el nombre real; catálogo de valores
   confirmado (ver CLAUDE.md §4-bis) — incluye una taxonomía temática incipiente útil para la
   Fase 6.

## Limitaciones y pendientes

- **Territorio sin verificar:** `data/referencia/divipola.csv` sigue sin existir. El diagnóstico
  no pudo normalizar `DEPARTAMENTO_HECHOS`/`MUNICIPIO_HECHOS` ni verificar el prefijo DANE de
  `CASO_NOTICIA`. El criterio de compuerta "100 % de valores territoriales mapeados o marcados
  no resoluble" **no se cumple todavía** por esta ausencia, no por una falla del código (probado
  contra un gazetteer sintético en `tests/fixtures/divipola_sintetico.csv`, incluidos homónimos).
- `eje tmeatico APLICA`, `UNID_DESCRIPCION` y las dos nuevas secciones de `SECC_DESCRIPCION` no
  tienen ficha de indicador ni definición formal todavía; quedan para I1/I5.
- El periodo real (10 meses) descarta pronósticos (I4) por ahora; se reevalúa cuando haya más lotes.
- `informe.md` no aplica la misma supresión `<5` que los CSV a los conteos que incrusta en el
  texto (ej. "0 relatos con mojibake"); no es sensible hoy pero se corrige antes de I1.
- ADRs 0003–0007 siguen con decisión provisional o pendiente (servicios adicionales, modelo de
  embeddings definitivo, respaldo cifrado): no bloquean I1, pero deben revisarse antes de I2–I4.

## Compuerta

**Aprobada con una condición abierta:** la persona aprobó grano, alcance y tratamiento de la
regla de prescripción. El criterio de normalización territorial queda pendiente de que se copie
DIVIPOLA real a `data/referencia/`; puede resolverse en paralelo a I1 sin bloquear su arranque,
siempre que I1 declare explícitamente qué filas quedan con territorio "no resoluble" mientras
tanto.

**Siguiente paso:** `/02-i1-base-indicadores`.
