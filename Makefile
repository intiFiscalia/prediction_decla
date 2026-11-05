.PHONY: instalar test lint fixtures diagnostico etl analitica-descriptiva nlp conocimiento fenomenos analitica emergencia prediccion app informe evaluar lote

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

# I4 — Fase 9: detección de atípicos (pronósticos y clasificación temática no son viables con
# el dataset real — ver reports/agregados/i4/viabilidad.md y docs/informes/I4_cierre.md).
# Necesita el lote_id que imprimió `make nlp` (sus embeddings de relato están en
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
