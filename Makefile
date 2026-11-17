.PHONY: instalar test lint fixtures diagnostico columnas-usadas etl analitica-descriptiva nlp conocimiento diagnostico-umbral anotar-menciones calibrar-umbral fenomenos anotar-fenomenos entrenar-clasificador-fenomenos clasificar-fenomenos-llm evaluar-clasificador-llm resumen-organizaciones resumen-fenomenos-no-listados promover-clasificador-fenomenos analitica emergencia prediccion app informe evaluar lote

# Instala dependencias solo desde wheelhouse/ (sin red), con todos los extras del proyecto.
instalar:
	uv sync --extra base --extra nlp --extra fenomenos --extra fenomenos_llm --extra analitica --extra app --extra dev --no-index --find-links wheelhouse

# Corre la suite de pruebas unitarias e integración sobre fixtures sintéticos.
test:
	uv run pytest

# Revisa estilo y tipos (ruff + mypy) sin modificar archivos.
lint:
	uv run ruff check . && uv run mypy src

# Regenera tests/fixtures/ con datos sintéticos reproducibles (nunca toca data/raw ni data/private).
fixtures:
	uv run python scripts/generar_fixtures.py

# I0 — Fase 1: diagnóstico de datos reales (bloqueado para Claude Code; lo ejecuta la persona).
diagnostico:
	uv run python -m decla.calidad.diagnostico

# Exporta CASOS/RELATOS originales con solo las columnas que el pipeline usa (lectura más fácil
# para la persona; nunca lo corre ni lo lee Claude Code). Escribe en data/private/columnas_usadas/.
columnas-usadas:
	uv run python scripts/exportar_columnas_usadas.py

# I1 — Fase 3: pipeline bronce→plata→entidades sobre datos reales.
etl:
	uv run python -m decla.ingesta.pipeline

# I1 — Fase 7 parcial: indicadores descriptivos + mapas + informe.html (reports/i1,
# reports/agregados/i1). Lee data/warehouse.duckdb en solo lectura (ya debe existir, vía `etl`).
analitica-descriptiva:
	uv run python -m decla.analitica.descriptiva

# I2 — Fase 4: procesamiento de RELATO (limpieza, segmentación, embeddings).
nlp:
	uv run python -m decla.texto.pipeline

# I2 — Fase 5: extracción de menciones con evidencia y confianza.
conocimiento:
	uv run python -m decla.conocimiento.pipeline

# Diagnóstico de la distribución real de confianza del clasificador zero-shot (sector/mecanismo),
# para recalibrar config/umbrales.yaml con evidencia del corpus real. Corre después de
# `conocimiento`. Escribe reports/agregados/diagnostico/umbral_zero_shot_*.csv.
diagnostico-umbral:
	uv run python -m decla.conocimiento.diagnostico_umbral

# Muestra estratificada y activa (confianza más incierta primero) de menciones de texto.menciones
# para que un analista confirme/rechace/corrija. Calificaciones en data/private/ (nunca las lee
# Claude Code). Por defecto el cupo se reparte entre sector y mecanismo.
anotar-menciones:
	uv run streamlit run src/decla/conocimiento/app_anotacion_menciones.py

# Une las calificaciones humanas de `anotar-menciones` con la confianza real de texto.menciones:
# precisión aproximada por umbral candidato (precision_por_umbral.csv) y códigos de mecanismo
# nuevo propuestos en "valor correcto" que la taxonomía todavía no cubre
# (candidatos_mecanismo_nuevo.csv). Solo agregados con supresión < 5. Corre después de
# anotar-menciones.
calibrar-umbral:
	uv run python scripts/calibrar_umbral_desde_anotacion.py

# I2 — Fase 6: descubrimiento y clasificación de fenómenos. Necesita el lote_id que imprimió
# `make nlp` (sus embeddings de segmento están en data/embeddings/<lote_id>/): make fenomenos
# LOTE_ID=<el-lote-id-de-make-nlp>
fenomenos:
	uv run python -m decla.fenomenos.pipeline --lote-id $(LOTE_ID)

# ADR 0024 — anotación de fenómenos por relato completo (multietiqueta), distinta de
# anotar-menciones. Calificaciones en data/private/ (nunca las lee Claude Code).
anotar-fenomenos:
	uv run streamlit run src/decla/fenomenos/app_anotacion_fenomeno.py

# ADR 0024 — entrena el clasificador de fenómenos sobre las calificaciones de anotar-fenomenos.
# Rechaza entrenar si algún código no alcanza config/umbrales.yaml:
# clasificador_fenomeno.minimo_ejemplos_por_codigo (CLAUDE.md §2.3). Necesita el lote_id que
# imprimió `make nlp`: make entrenar-clasificador-fenomenos LOTE_ID=<el-lote-id-de-make-nlp>
entrenar-clasificador-fenomenos:
	uv run python -m decla.fenomenos.pipeline_clasificador --lote-id $(LOTE_ID)

# ADR 0027 — el LLM local (Qwen2.5-14B, MLX) clasifica el 100% de los relatos (sin clasificador
# rápido filtrando qué revisar: la persona priorizó rigor sobre velocidad). Por defecto solo
# procesa relatos sin fila origen=inferido_modelo_llm todavía (incremental entre lotes); agregar
# FORZAR=1 para reclasificar todo (al iterar el prompt). LIMITE=N procesa como máximo N relatos
# (muestra aleatoria con semilla fija, reproducible) — útil para iterar rápido mientras la data
# es de prueba/entrenamiento, no el universo real. Necesita el modelo descargado (`uv run python
# scripts/descargar_modelos.py --solo qwen2.5-14b-instruct-4bit`, ~8-9GB, una sola vez).
clasificar-fenomenos-llm:
	uv run python -m decla.fenomenos.pipeline_clasificador_llm $(if $(FORZAR),--forzar,) $(if $(LIMITE),--limite $(LIMITE),)

# ADR 0027 — compara las predicciones del LLM contra la anotación humana confirmada
# (make anotar-fenomenos) y escribe reports/agregados/i4/clasificador_fenomenos_llm_metricas.md.
# Es la métrica para decidir si el prompt necesita otra iteración antes de promover.
evaluar-clasificador-llm:
	uv run python scripts/evaluar_clasificador_llm.py

# ADR 0028 — cuenta las organizaciones criminales que el LLM encontró mencionadas
# explícitamente en los relatos (campo abierto, raro en los datos) y escribe
# reports/agregados/i4/candidatos_organizacion_criminal.csv. Reporte de candidatos, no una lista
# aprobada: normalizar variantes del mismo nombre es una decisión humana antes de usarlos en
# indicadores oficiales.
resumen-organizaciones:
	uv run python scripts/resumen_organizaciones_mencionadas.py

# ADR 0029 — cuenta los fenómenos que el LLM describió como relevantes pero fuera de la
# taxonomía congelada (en vez de forzarlos en el código "más parecido") y escribe
# reports/agregados/i4/candidatos_fenomeno_no_listado.csv. Reporte de candidatos, no un código
# nuevo: formalizarlo es un taller de revisión humana.
resumen-fenomenos-no-listados:
	uv run python scripts/resumen_fenomenos_no_listados.py

# ADR 0025 — copia una versión entrenada hacia fenomenos.asignacion_fenomeno (la que ya leen
# indicadores, asociaciones, atípicos y la app). Revisa antes
# reports/agregados/i4/clasificador_fenomenos_metricas.md. Correr DESPUÉS de `make analitica`
# (que reconstruye asignacion_fenomeno desde cero) y ANTES de `make emergencia`/`make
# prediccion`/`make app`: make promover-clasificador-fenomenos VERSION_MODELO=<el que imprimió
# entrenar-clasificador-fenomenos>
promover-clasificador-fenomenos:
	uv run python scripts/promover_clasificador_fenomenos.py --version-modelo $(VERSION_MODELO) --confirmar

# I3 — Fase 7: indicadores, territorio, asociaciones.
analitica:
	uv run python -m decla.analitica.pipeline

# I3 — Fase 8: detección de tendencias y fenómenos emergentes.
emergencia:
	uv run python -m decla.emergencia.pipeline

# I4 — Fase 9: detección de atípicos + pronósticos de frecuencia por fenómeno (ADR 0016: sin
# umbral mínimo de historia, se construye con la disponible). Clasificación temática sigue sin
# ser viable (falta anotación) — ver reports/agregados/i4/viabilidad.md y docs/informes/
# I4_cierre.md. Necesita el lote_id que imprimió `make nlp` (sus embeddings de relato están en
# data/embeddings/<lote_id>/): make prediccion LOTE_ID=<el-lote-id-de-make-nlp>
prediccion:
	uv run python -m decla.prediccion.pipeline --lote-id $(LOTE_ID)

# I3 — Fase 11: aplicación Streamlit local de consulta y validación.
app:
	uv run streamlit run src/decla/app/main.py

# Ensambla informe.html a partir de lo que ya calculó `analitica-descriptiva` (hoy son el mismo
# paso: decla.analitica.descriptiva calcula y ensambla en una sola corrida; separar cálculo de
# render queda para cuando el costo de recalcular justifique cachear — ver ADR 0009).
informe: analitica-descriptiva

# I4 — Fase 10: evaluación consolidada (métricas históricas + recalculadas en vivo) en
# reports/agregados/evaluacion/v1.md.
evaluar:
	uv run python -m decla.evaluacion.pipeline

# Procesa un lote nuevo (I4 — Fase 12): valida esquema, clasifica nuevo/modificado/repetido por
# caso_notica, guarda historia de cambios y calcula deriva. No recalcula nlp/fenómenos/analítica
# automáticamente (paso manual, ver docs/manual_operacion.md).
lote:
	uv run python -m decla.ingesta.lote --archivo $(ARCHIVO)
