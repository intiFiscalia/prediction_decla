# 0028 — Organización criminal mencionada explícitamente en el relato (campo abierto, sin taxonomía)

- **Fecha:** 2026-11-17
- **Estado:** aceptada

## Contexto

La persona pidió un indicador adicional: identificar qué organización criminal nombrada (p. ej.
"el grupo de liberación nacional ELF") está detrás de cada relato, cuando el relato la menciona
explícitamente — raro, pero cuando aparece es un dato valioso (permite, por ejemplo, saber qué
organización reportó más casos o a cuál se le incautó más dinero).

Investigué el repo antes de diseñar: no existe ningún catálogo de organizaciones criminales
(gazetteer, YAML, tabla) ni ninguna ADR previa sobre el riesgo de nombrar una organización
específica en los resultados. El patrón más cercano es el EntityRuler/gazetteer de
`decla.texto.pipeline_spacy` (listas cerradas: instituciones, territorio) y el patrón de
"candidatos nuevos" de ADR 0020 (mecanismos de lavado no previstos en el diccionario: se cuentan,
nunca se auto-aprueban).

La persona confirmó que es, por naturaleza, un **conjunto abierto**: no hay una lista cerrada de
organizaciones a priori — el nombre sale del texto mismo del relato, tal como está escrito.

## Decisión

1. **Extracción en el mismo paso del LLM, sin llamadas adicionales.** `clasificador_llm.
   construir_prompt` (ADR 0027) ahora también pide `organizacion_mencionada`: el nombre tal como
   aparece en el relato, o `null` si no se menciona ninguna explícitamente. El prompt es
   explícito: nunca inferir o adivinar una organización que el relato no nombra.
2. **Campo abierto, gobernado igual que mecanismos nuevos (ADR 0020), no como taxonomía
   cerrada.** `fenomenos.organizacion_mencion_modelo` (registro_uid, organizacion_nombre_crudo,
   confianza, origen, version_modelo, run_id) guarda el nombre crudo, sin normalizar. `make
   resumen-organizaciones` cuenta relatos distintos por nombre y escribe
   `reports/agregados/i4/candidatos_organizacion_criminal.csv` — un reporte de candidatos, nunca
   una lista aprobada. Variantes del mismo nombre ("FARK" / "Fark-EP" / errores de transcripción)
   no se normalizan automáticamente: es una decisión humana antes de construir cualquier
   indicador oficial "por organización".
3. **Ningún indicador oficial todavía.** Esta ADR construye la extracción y el reporte de
   candidatos — no toca `decla.analitica.indicadores` ni territorio. Indicadores reales ("la
   organización X reportó más casos", "a la organización Y se le incautó más dinero") requieren
   primero que la persona revise `candidatos_organizacion_criminal.csv` y decida la normalización
   de nombres; es un incremento aparte una vez exista esa decisión.
4. **Mismo rigor que el resto del proyecto (CLAUDE.md §2.3), explícito para este campo en
   particular**: que un relato mencione una organización no prueba que esa organización participó
   en el hecho — es una afirmación del relato, no un hecho verificado. Cualquier salida futura que
   muestre resultados "por organización" debe decirlo explícitamente, igual que ya se hace con
   fenómenos y sectores.
5. **Robustez de parseo del LLM, encontrada al correr sobre datos reales:** Qwen2.5-14B a veces
   agrega texto narrativo después del JSON válido, o lo envuelve en una valla de markdown, aunque
   el prompt pida solo JSON. `clasificador_llm._decodificar_primer_json` ahora decodifica el
   primer objeto JSON balanceado e ignora lo demás, en vez de exigir que toda la respuesta sea
   JSON puro — corregido junto con esta ADR porque se descubrió en la misma corrida real.

## Consecuencias

- `pipeline_clasificador_llm.ejecutar_clasificacion_llm` ahora también escribe (cuando aplica)
  en `fenomenos.organizacion_mencion_modelo`, en el mismo paso que clasifica fenómenos — sin
  costo adicional de tiempo de LLM.
- El campo es raro en los datos por diseño (la persona lo confirmó): la mayoría de los relatos
  tendrán `organizacion_mencionada = null`. No es un error ni una señal de que el prompt falla.
- Queda pendiente, a decisión futura de la persona: tabla de normalización de nombres (similar a
  `config/diccionarios/mecanismos_expresiones.yaml`) y los indicadores reales por organización en
  `decla.analitica.indicadores`.
