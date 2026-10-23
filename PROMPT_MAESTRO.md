# Prompt maestro para ejecutar el plan con Claude Code

## Cómo usar este kit

1. Crea una carpeta vacía para el proyecto y copia dentro todo el contenido del kit
   (`CLAUDE.md`, `.claude/`, `docs/plan_trabajo.md`, este archivo).
2. Inicializa git en esa carpeta (`git init`).
3. **No copies todavía los datos reales.** Claude Code envía al modelo lo que lee; por eso el kit
   bloquea `data/raw/` y `data/private/` y obliga a desarrollar con datos sintéticos. Los datos reales
   se copian cuando el arranque termine, y los procesas tú con `make`.
4. Abre Claude Code en la carpeta y pega el **prompt de arranque** (abajo).
5. Después ejecuta los comandos en orden, uno por sesión, aprobando cada compuerta:

| Orden | Comando | Fases del plan | Qué obtienes | Compuerta |
| --- | --- | --- | --- | --- |
| 0 | `/00-arranque` | 2 (parcial) | Repositorio, entorno fuera de línea, datos sintéticos con los defectos reales | Pruebas verdes sin internet |
| 1 | `/01-i0-diagnostico` | 1, 2 | Diagnóstico completo del dataset, unidad de análisis, ADRs | Grano y supuestos aprobados |
| 2 | `/02-i1-base-indicadores` | 3, 7 (parcial), 11 (parcial) | ETL trazable, indicadores descriptivos, mapas, informe | Conteos conciliados y validados |
| 3 | `/03-i2-texto-fenomenos` | 4, 5, 6, 10 (parcial) | NLP, menciones, sectores, buscador semántico, taxonomía v1.0 | Taxonomía aprobada y métricas en umbral |
| 4 | `/04-i3-relaciones-emergencia` | 7, 8, 11 | Asociaciones, territorio, alertas con retroprueba, app local | Falsas alarmas aceptadas, app probada |
| 5 | `/05-i4-prediccion-operacion` | 9, 10, 12 | Pronósticos viables, evaluación, operación por lotes | Modelos superan al ingenuo, 3 lotes sin intervención |

Puedes añadir notas al comando, por ejemplo: `/01-i0-diagnostico el equipo tiene 32 GB de RAM y sin GPU`.

**Consejos de operación**
- Una sesión por incremento (o por bloque en I2); usa `/clear` entre incrementos para empezar con
  contexto limpio: `CLAUDE.md` y los informes de cierre llevan la memoria entre sesiones.
- Cuando Claude Code te pida ejecutar un objetivo de `make` sobre datos reales, hazlo tú en la
  terminal y avísale cuando termine; solo debe leer `reports/agregados/`.
- Revisa cada `docs/decisiones/` y `docs/informes/I<n>_cierre.md` antes de aprobar una compuerta.
- Si cambian las reglas o aparecen nuevos hallazgos, actualiza `CLAUDE.md` §4 y §6.

---

## Prompt de arranque (pegar en la primera sesión)

```text
Vas a implementar, por incrementos, la herramienta local de analítica de fenómenos asociados al lavado
de activos descrita en docs/plan_trabajo.md.

Antes de hacer nada:
1. Lee completos CLAUDE.md y docs/plan_trabajo.md.
2. Confírmame en máximo 10 líneas: (a) el objetivo, (b) las reglas de privacidad que vas a respetar
   (en especial que nunca leerás data/raw ni data/private y que desarrollarás solo con datos
   sintéticos), (c) los 5 hallazgos de la muestra que más condicionan el diseño, y (d) el orden de
   incrementos y sus compuertas.
3. Lista las dudas que bloquean el arranque, con opciones concretas para que yo elija.

No escribas código en esta respuesta. Cuando yo confirme, ejecuta /00-arranque.

Reglas de trabajo para todo el proyecto:
- Trabaja en modo plan al inicio de cada incremento y espera mi aprobación.
- Usa la lista de tareas y haz commits pequeños por tarea.
- Toda regla de limpieza va en config/ y tiene prueba unitaria con fixtures sintéticos.
- No avances de incremento sin que yo apruebe la compuerta.
- Si algo del plan choca con los hallazgos de los datos, prevalecen los datos: documenta la
  diferencia en docs/decisiones/ y pregúntame.
- Distingue siempre registrado / extraído / inferido; nunca presentes correlación como causa ni
  menciones como hechos; nada se asigna a personas o empresas.
```

---

## Prompt de reanudación (cualquier sesión nueva)

```text
Retomamos el proyecto. Lee CLAUDE.md, el último docs/informes/I<n>_cierre.md y git log -20.
Dime en 5 líneas en qué incremento estamos, qué tareas quedan abiertas y qué decisión mía está
pendiente. No escribas código hasta que te confirme el siguiente paso.
```

## Prompt de revisión independiente (antes de cada compuerta)

```text
Actúa como revisor/a independiente que no escribió este código. Revisa el incremento I<n> contra
docs/plan_trabajo.md (fases correspondientes y sección 9) y CLAUDE.md §2:
- ¿Algún camino del código puede imprimir, registrar o exportar texto de relatos o identificadores
  sin enmascarar? Busca en logs, excepciones, exportes y la app.
- ¿Hay fuga temporal en evaluación o en variables de modelos?
- ¿Algún indicador o texto generado afirma causalidad, incidencia real o responsabilidad?
- ¿Cada métrica de la compuerta está calculada y comparada con su umbral?
- ¿Las reglas de normalización conservan el valor original y tienen prueba?
Entrega hallazgos priorizados con archivo y línea, y no corrijas nada hasta que yo lo apruebe.
```
