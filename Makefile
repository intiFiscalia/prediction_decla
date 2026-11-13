.PHONY: instalar test lint fixtures diagnostico columnas-usadas etl analitica-descriptiva nlp conocimiento diagnostico-umbral anotar-menciones calibrar-umbral fenomenos analitica emergencia prediccion app informe evaluar lote

# Instala dependencias solo desde wheelhouse/ (sin red), con todos los extras del proyecto.
instalar:
	uv sync --extra base --extra nlp --extra fenomenos --extra analitica --extra app --extra dev --no-index --find-links wheelhouse

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
