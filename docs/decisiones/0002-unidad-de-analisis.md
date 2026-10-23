# 0002 — Unidad de análisis (grano de una fila de CASOS)

- **Fecha:** 2026-10-23
- **Estado:** **aceptada** (compuerta I0, aprobada por la persona el 2026-10-23)

## Contexto

El plan (Fase 1, plan_trabajo.md) exige fijar qué representa una fila de CASOS antes de construir
cualquier ETL o indicador: evita contar mal (si una noticia aparece varias veces) y localizar mal
(si distintas filas de la misma noticia tienen territorio distinto). `decla.calidad.cardinalidad`
ya calcula la evidencia necesaria (`proponer_hipotesis_grano`) y se ejecutó sobre fixtures
sintéticos para validar que el código funciona; falta ejecutarlo sobre `data/raw/` real
(`make diagnostico`) y que la persona decida con esa evidencia.

## Opciones consideradas

1. **Una fila = una noticia criminal.** Válida si `n_caso_noticia_unicos / n_filas ≈ 1` y los
   grupos con DELITO/DESPACHO/fecha distintos para la misma noticia son raros.
2. **Una fila = noticia × delito (o diligencia/actuación).** Válida si una fracción relevante de
   noticias tiene varias filas con esos campos distintos entre sí.
3. **Indeterminado / mezcla de unidades de registro.** Si ninguna de las dos anteriores domina
   claramente, o si hay evidencia de que el criterio cambió en el tiempo (distintos sistemas o
   prácticas de captura).

## Decisión

**Opción 1: una fila = una noticia criminal.** `make diagnostico` corrió sobre las 978 filas
reales de `data/raw/` (2026-10-23): 978 `CASO_ID` únicos = 978 `CASO_NOTICIA` únicos = 978 filas,
0 duplicados exactos, 0 duplicados parciales (`hipotesis_grano.csv`, puntaje 1.00). La persona
aprobó esta hipótesis en la compuerta de I0 sin reservas.

No hace falta una llave agregada adicional (`caso` o `grupo_conexo`) para I1: con grano 1:1, la
tabla `noticia_criminal` puede ser, en esencia, `registros_limpios` con `registro_uid` como llave,
sin una capa de deduplicación previa. Si llegan lotes futuros con duplicados o multidelito, esta
decisión se reabre, no se asume que seguirá siendo así.

## Consecuencias

- `decla.ingesta` (I1) puede construir `noticia_criminal` directamente desde `registros_limpios`
  sin lógica de deduplicación por `CASO_NOTICIA`; si aparece, es un hallazgo de calidad a reportar,
  no el caso esperado.
- Los indicadores de volumen (plan_trabajo.md §8.1) pueden reportarse en una sola unidad
  (registros = noticias) para este dataset; seguir calculando las tres unidades (registros,
  noticias únicas, grupos conexos) solo donde el costo es bajo, como salvaguarda ante lotes futuros.
