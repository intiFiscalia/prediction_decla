# 0002 — Unidad de análisis (grano de una fila de CASOS)

- **Fecha:** 2026-10-23
- **Estado:** propuesta — **pendiente de aprobación de la persona con datos reales**

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

**Pendiente.** Sobre fixtures sintéticos (que plantan ambos patrones a propósito), el código
produce correctamente las tres hipótesis rankeadas con su evidencia; eso confirma que el
diagnóstico está listo, no decide por sí mismo cuál aplica a los datos reales.

Cuando la persona ejecute `make diagnostico` y yo lea `reports/agregados/diagnostico/informe.md`
y `hipotesis_grano.csv`, se completa esta sección con: la hipótesis elegida, el umbral de
confianza que la sostiene, y si hace falta una llave agregada adicional (`caso` o `grupo_conexo`,
CLAUDE.md §3.3) para los análisis que requieren una noticia por fila.

## Consecuencias

- Toda tabla de entidades analíticas de I1 (`noticia_criminal`, `caso`) depende de esta decisión.
- Si el grano resulta ser "noticia × delito", los indicadores de volumen (plan_trabajo.md §8.1)
  deben reportarse en las tres unidades (registros, noticias únicas, grupos conexos) desde el
  principio, no como ajuste posterior.
