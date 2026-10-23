# 0006 — Orquestación: Makefile vs. Prefect/Dagster

- **Fecha:** 2026-10-23
- **Estado:** decisión provisional confirmada para I0–I2; revisar en I4 (operación continua)

## Contexto

plan_trabajo.md §5.3 condiciona el orquestador a la frecuencia de llegada de lotes nuevos y a si
se permiten servicios adicionales (pregunta abierta en CLAUDE.md §6 y en el ADR 0003). Hoy hay un
solo lote (`data/raw/`) y una sola persona ejecutando `make <objetivo>` manualmente.

## Opciones consideradas

1. **Makefile + DAG implícito por dependencia de archivos.** Ya implementado (`/00-arranque`): cada
   objetivo (`diagnostico`, `etl`, `nlp`, ...) es un paso explícito que la persona dispara a mano.
   Sin reintentos automáticos ni programación.
2. **Prefect (servidor local) o Dagster.** Necesario si aparecen lotes recurrentes con necesidad de
   reintentos, programación o un grafo de dependencias más complejo que "paso A antes que paso B"
   (I4, Fase 12: ingesta de lotes, recálculo incremental, monitoreo de deriva).

## Decisión

Mantener el **Makefile** como orquestador mientras el flujo sea de ejecución manual, lote único y
sin reintentos automáticos. Revisar esta decisión al llegar a I4 (Fase 12, "procedimiento de
ingesta de lotes"), cuando haya evidencia real de con qué frecuencia llegan lotes nuevos.

## Consecuencias

- Cada objetivo de `make` debe seguir siendo idempotente y registrar su ejecución en
  `meta.ejecuciones` (ya lo hace `diagnostico` vía `RegistroEjecucion`): eso es lo que permitiría
  migrar a un orquestador real sin rediseñar los pasos, solo la capa que los dispara.
- Si en I4 se decide Prefect/Dagster, hay que desactivar su telemetría por defecto (CLAUDE.md
  §2.2), igual que se hizo con Streamlit en el ADR 0001.
