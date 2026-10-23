# 0003 — Almacenamiento analítico: DuckDB+Parquet vs. PostgreSQL

- **Fecha:** 2026-10-23
- **Estado:** decisión provisional confirmada para I0–I1; revisar en I2 si cambian los supuestos

## Contexto

plan_trabajo.md §5.3 deja esto condicionado a dos preguntas que CLAUDE.md §6 registra como
abiertas: cuántos usuarios concurrentes escribirán (anotación en I2+) y si la máquina permite
instalar servicios adicionales. Con el hardware confirmado (Apple M5, 16 GB RAM, una sola persona
desarrollando y una persona operando `make` sobre los datos reales), no hay hoy evidencia de
escritura concurrente.

## Opciones consideradas

1. **DuckDB + Parquet.** Un solo proceso escritor; la app de consulta (I3) abre en solo lectura
   (`decla.comun.duckdb_io.conectar(..., solo_lectura=True)`, ya implementado). Cero servicios que
   administrar.
2. **PostgreSQL + PostGIS + pgvector.** Necesario si varias personas anotan a la vez en la cola de
   revisión (I2) con escrituras concurrentes reales, o si se requieren roles finos a nivel de base
   de datos.

## Decisión

Mantener **DuckDB + Parquet** para I0–I1. `src/decla/comun/duckdb_io.py` ya está escrito para
soportar el cambio sin reescritura amplia (la capa de acceso está centralizada ahí, no dispersa).

**Pendiente de confirmar antes de I2:** cuántas personas van a anotar simultáneamente en la cola
de revisión y si la máquina de producción permite instalar PostgreSQL. Si la respuesta es "más de
una persona escribiendo a la vez", este ADR se reabre antes de construir la cola de revisión, no
después.

## Consecuencias

- Mientras la decisión no cambie, cualquier acceso de escritura fuera de `make <objetivo>`
  (ejecutado por la persona, nunca por Claude Code) puede romper la base por el límite de un solo
  escritor.
- Migrar a PostgreSQL más adelante implica reescribir `comun/duckdb_io.py`, no el resto del
  pipeline, si las consultas se mantienen en SQL estándar.
