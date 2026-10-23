# 0007 — Plan de respaldo cifrado

- **Fecha:** 2026-10-23
- **Estado:** propuesta — **pendiente de definición con la persona responsable de datos**

## Contexto

plan_trabajo.md (Fase 2, riesgos) señala una sola máquina como punto único de falla y exige copias
de respaldo cifradas con prueba de restauración. CLAUDE.md §2.1 trata `data/raw/`, `data/private/`
y `data/warehouse.duckdb` como bloqueados para Claude Code; cualquier mecanismo de respaldo debe
preservar ese bloqueo (no puede exponer esas rutas a un servicio que Claude Code pueda leer).

Esta decisión depende de información que todavía no existe en el repositorio: qué exige la
oficina jurídica sobre conservación de bitácoras y reserva sumarial (CLAUDE.md §6, plan_trabajo.md
sección 12, pregunta 14), y qué medios de respaldo están autorizados institucionalmente.

## Opciones consideradas

1. **Cifrado en reposo a nivel de disco/volumen** (p. ej. FileVault en la máquina de producción) +
   copia periódica a un medio físico autorizado, sin que el proceso de respaldo pase por ninguna
   herramienta con acceso a red.
2. **Cifrado por archivo** (p. ej. `age` o `gpg` sobre el `.duckdb` y los Parquet de `data/private/`
   antes de copiarlos), más granular pero añade un paso manual por lote.
3. **Sin respaldo automatizado por ahora**, solo copia manual verificada por la persona, hasta que
   la oficina jurídica confirme requisitos de retención.

## Decisión

**Pendiente.** No se implementa ningún mecanismo de respaldo todavía: hacerlo sin la confirmación
jurídica sobre retención de bitácoras arriesga guardar (o borrar) algo que no corresponde. Este
ADR se completa cuando la persona traiga esa respuesta.

## Consecuencias

- Hasta que se resuelva, la única copia de los datos reales es la que la persona mantenga fuera de
  este repositorio; Claude Code no participa en absoluto en esa copia (no puede leer `data/raw/`
  ni `data/private/` para respaldarlos ni para verificarlos).
- Cuando se elija un mecanismo, debe probarse una restauración completa al menos una vez antes de
  depender de él (plan_trabajo.md, Fase 2, riesgos).
