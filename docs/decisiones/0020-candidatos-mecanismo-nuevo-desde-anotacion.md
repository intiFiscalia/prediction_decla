# 0020 — Candidatos a mecanismo nuevo desde la anotación humana

- **Fecha:** 2026-11-09
- **Estado:** aceptada

## Contexto

Durante el etiquetado con `app_anotacion_menciones.py` (ADR 0019), la persona identificó un
caso real (lingotes de oro incautados sin documentación de origen → mecanismo de lavado vía
minería ilegal) que requería una corrección con razonamiento, no una lectura literal del texto.
Dos necesidades quedaron explícitas:

1. Registrar el porqué de una corrección cuando no es obvia (campo `notas`, ya agregado).
2. Que si el método identificado **no es ninguno de los 12 códigos actuales**, el sistema no lo
   descarte — la persona ya puede escribir cualquier código nuevo en "valor correcto" (el campo
   es texto libre), pero nada conectaba esa corrección de vuelta a la taxonomía
   (`config/categorias_menciones.yaml`) ni al diccionario explícito. El objetivo explícito de la
   persona: una herramienta que "evolucione al mismo nivel que el crimen organizado", no una
   lista cerrada de 12 técnicas.

## Decisión

1. `data/private/anotacion_menciones/calificaciones.csv` gana una columna `notas` (texto libre,
   opcional). Migración automática y única si el archivo ya existía sin esa columna
   (`_migrar_encabezado_si_falta_notas`): nunca borra calificaciones previas.
2. `decla.conocimiento.herramienta_anotacion_menciones.identificar_candidatos_mecanismo_nuevo`
   (pura, testeada): cuenta, entre las correcciones (`decision == "corregida"`,
   `categoria == "mecanismo"`), los códigos de `valor_corregido` que NO están en el vocabulario
   vigente (`decla.conocimiento.zero_shot.cargar_vocabulario("mecanismo")`). Nunca agrega nada
   solo: es una señal para que la persona decida formalizar.
3. `scripts/calibrar_umbral_desde_anotacion.py` ahora escribe un segundo reporte,
   `reports/agregados/diagnostico/candidatos_mecanismo_nuevo.csv` (código propuesto + conteo,
   con supresión de celdas < 5 igual que el resto de `reports/agregados/`). No incluye
   `mencion_id` ni `notas` en este reporte agregado (la persona ya tiene esa evidencia completa
   en su propio CSV de calificaciones; no hace falta que Claude Code la vea para decidir si un
   código nuevo merece formalizarse).

## Consecuencias

- Formalizar un candidato (agregar definición a `categorias_menciones.yaml` y expresiones a
  `mecanismos_expresiones.yaml`) sigue siendo una edición manual de la persona — este cambio solo
  hace visible la señal agregada, no la automatiza. Automatizar la escritura de la taxonomía sin
  revisión humana violaría CLAUDE.md §2.3.
- `identificar_candidatos_mecanismo_nuevo` solo mira correcciones de categoría `mecanismo`; si
  surge el mismo patrón para `sector` (CIIU), es una extensión simétrica pendiente, no incluida
  en esta ronda porque el pedido concreto fue sobre mecanismos de lavado.
- Cada vez que se formalice un código nuevo, `cargar_vocabulario("mecanismo")` lo recoge solo
  (no hay lista hardcodeada de 12 en el código de detección de candidatos), así que el reporte
  deja de marcarlo como "nuevo" automáticamente en la siguiente corrida.
