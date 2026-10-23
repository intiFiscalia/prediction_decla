# 0004 — Granularidad temporal de indicadores y pronósticos

- **Fecha:** 2026-10-23
- **Estado:** propuesta — **pendiente de datos reales**

## Contexto

plan_trabajo.md §5.3 condiciona la granularidad (semana/mes/trimestre) al volumen real y al uso
previsto (sección 12 del plan, pregunta 16, también abierta). CLAUDE.md §4.14 advierte que la
muestra observada cubre un solo año (marzo–octubre 2026): con un solo año no hay estacionalidad ni
historia suficiente para pronósticos, independientemente de la granularidad elegida.

`decla.calidad.temporal.resumir_temporal` ya calcula, por diseño, el número de meses con datos y
compara contra el umbral de 36 meses que plan_trabajo.md §8.4 recomienda para pronósticos viables;
ese cálculo corre hoy sobre fixtures sintéticos (que sí cubren 2021–2026 a propósito, para probar
el código) y debe repetirse sobre datos reales.

## Opciones consideradas

1. **Mensual.** Más detalle, pero con pocos registros por fenómeno/territorio puede producir
   series ruidosas (celdas pequeñas, Moran/LISA poco estables).
2. **Trimestral.** Más estable si el volumen mensual es bajo; retrasa la detección de emergencia
   (plan_trabajo.md §8.5 pide persistencia de 2–3 periodos, que en trimestral son 6–9 meses).
3. **Granularidad mixta.** Mensual para indicadores descriptivos e indicadores de emergencia
   (CUSUM/EARS necesitan resolución fina); trimestral o anual para reportes ejecutivos y para
   cualquier pronóstico, si el historial lo permite.

## Decisión

**Pendiente.** Recomendación provisional (a confirmar con el informe de diagnóstico real):
granularidad mensual como base de cómputo interno (es la que ya usa `temporal.py` y los
indicadores de volumen), con agregación a trimestral/anual solo en la capa de presentación
(Fase 11) si el volumen mensual real resulta demasiado bajo por territorio.

## Consecuencias

- Si el periodo real sigue siendo de un solo año, I4 (pronósticos) queda explícitamente fuera de
  alcance hasta acumular más lotes (CLAUDE.md §4.14), independientemente de esta decisión.
- La granularidad elegida aquí determina el `offset` de volumen total en los modelos de línea
  base de emergencia (plan_trabajo.md §8.5): cambiarla después de construir esos modelos implica
  recalibrarlos, no solo re-agregar.
