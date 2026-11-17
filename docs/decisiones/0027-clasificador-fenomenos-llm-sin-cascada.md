# 0027 — El LLM local clasifica el 100% de los relatos; se retira la cascada con el clasificador rápido

- **Fecha:** 2026-11-17
- **Estado:** aceptada

## Contexto

ADR 0026 (el mismo día) diseñó una cascada: el clasificador rápido (sklearn, ADR 0024) cubría el
100% de los registros y el LLM local solo reclasificaba los relatos que el clasificador rápido
marcaba `no_clasificado`. La razón era de tiempo: Qwen2.5-14B tarda ~38 segundos por relato en
este hardware, y millones de registros tocados uno por uno tomarían más de un año.

La persona rechazó esa cascada explícitamente: "no quiero clasificadores rápidos, necesito que
sean rigurosos para lograr el detalle necesario". El riesgo real de la cascada no es solo
velocidad — es que el clasificador rápido puede estar **confiadamente equivocado** en exactamente
los casos límite que motivaron usar un LLM en primer lugar (una similitud de embeddings alta no
garantiza el razonamiento contextual correcto). Filtrar por "el clasificador rápido dijo
`no_clasificado`" no detecta esos errores confiados — solo detecta la incertidumbre del propio
clasificador rápido, no la corrección del resultado. Priorizar rigor sobre velocidad es una
decisión legítima para una herramienta de priorización fiscal: el costo de un falso negativo/
positivo en un caso de lavado de activos pesa más que el costo de tiempo de cómputo.

También se aclaró qué significa "reentrenar" cuando la persona pidió que Claude Code itere el
modelo si no logra el detalle necesario: Qwen2.5-14B se usa por *prompting* (zero-shot), sin
afinamiento de pesos en este hardware (16GB, sin GPU CUDA — un LoRA de un modelo de 14B
probablemente no entra en memoria para entrenar, solo para inferencia). "Reentrenar" aquí es un
ciclo de ingeniería de prompt: medir error por código contra la anotación humana, ajustar los
criterios/ejemplos del prompt, volver a medir — no actualización de pesos.

## Decisión

1. **Se retira la cascada.** `decla.fenomenos.pipeline_clasificador_llm` ya no lee ninguna salida
   del clasificador rápido ni filtra por confianza ajena: clasifica con el LLM **todos** los
   `registro_uid` de `texto.relato_procesado`.
2. **Reprocesamiento incremental por defecto, forzado explícito para iterar.** Por defecto, cada
   corrida de `make clasificar-fenomenos-llm` solo procesa `registro_uid` sin fila
   `origen="inferido_modelo_llm"` todavía (nuevos desde la corrida anterior) — así los lotes
   anuales nuevos, mucho más chicos que el histórico completo, se clasifican rápido. `make
   clasificar-fenomenos-llm FORZAR=1` reclasifica todo, para medir el efecto de un prompt nuevo
   sobre la muestra completa. El procesamiento inicial del histórico completo puede tardar horas
   o días según el volumen real — se corre una sola vez, en background, no en el camino
   interactivo.
3. **Métrica para iterar, nunca sobre el relato real.** `decla.fenomenos.evaluacion_clasificador_llm`
   (`make evaluar-clasificador-llm`) compara las predicciones del LLM contra
   `data/private/anotacion_fenomenos/calificaciones.csv` (la anotación humana confirmada) y
   escribe `reports/agregados/i4/clasificador_fenomenos_llm_metricas.md` (precisión/
   exhaustividad/F1 por código, mismo patrón que `clasificador.py`). Esta es la única pieza que
   Claude Code lee para decidir si un código necesita mejor prompt — sigue sin leer relatos
   reales, enmascarados o no (ADR 0026 punto 5, vigente).
4. **El ciclo de iteración es manual y explícito, por código:**
   - `make clasificar-fenomenos-llm` (o con `FORZAR=1`)
   - `make evaluar-clasificador-llm`
   - Si un código sale con precisión/exhaustividad insuficiente: ajustar su criterio de
     "confirmar"/"caso límite" en `herramienta_anotacion_fenomeno.DESCRIPCION_CODIGO` (la misma
     fuente que ya usa el prompt — nunca un criterio distinto inventado aparte) y repetir.
   - Repetir hasta que las métricas convenzan, código por código — igual criterio que ADR 0025
     con el F1 del clasificador rápido: no hay un umbral numérico de "aceptable" impuesto por
     adelantado, lo decide la persona mirando la tabla.
5. **El clasificador sklearn (ADR 0024) no se borra, pero sale del camino de producción.** Sigue
   entrenable (`make entrenar-clasificador-fenomenos`) y probado, por si se decide usarlo para
   otra cosa en el futuro (nadie pidió borrarlo). `docs/manual_operacion.md` ya no lo incluye en
   la secuencia recomendada.
6. **Vigente de ADR 0026, sin cambios:** el modelo (Qwen2.5-14B-Instruct-4bit vía `mlx-lm`), el
   linaje (`origen="inferido_modelo_llm"`, esquema compatible con
   `scripts/promover_clasificador_fenomenos.py` sin tocarlo), el determinismo
   (`temperatura=0.0` + semilla fija) y que Claude Code nunca lee relatos reales.

## Consecuencias

- El procesamiento del histórico completo con millones de registros reales puede tomar
  semanas corriendo continuamente — es una decisión informada, no una sorpresa: se documenta
  aquí para que quede claro desde antes, no se descubra a mitad de una corrida real.
- `seleccionar_para_escalar` (la función de la cascada de ADR 0026) se eliminó de
  `clasificador_llm.py`; no queda código muerto de la cascada retirada.
- `fenomenos.asignacion_fenomeno_modelo` puede acumular varias `version_modelo` del LLM a lo
  largo del tiempo (una por corrida incremental) — es coherente con que la tabla sea histórica y
  con que la promoción (`--version-modelo`) siga siendo explícita y por versión, no automática
  (ADR 0025 punto 2, sin cambios).
- El piloto de anotación de ADR 0024 (50-100/código, doble anotación ≥20%, kappa≥0.6) sigue
  siendo la base de verdad contra la que se mide el LLM — sin eso, `evaluar-clasificador-llm` no
  tiene con qué comparar.
