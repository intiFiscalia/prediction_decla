.PHONY: instalar test lint fixtures diagnostico etl analitica-descriptiva nlp conocimiento fenomenos analitica emergencia prediccion app informe

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

# I2 — Fase 6: descubrimiento y clasificación de fenómenos.
fenomenos:
	uv run python -m decla.fenomenos.pipeline

# I3 — Fase 7: indicadores, territorio, asociaciones.
analitica:
	uv run python -m decla.analitica.pipeline

# I3 — Fase 8: detección de tendencias y fenómenos emergentes.
emergencia:
	uv run python -m decla.emergencia.pipeline

# I4 — Fase 9: pronósticos y detección de atípicos.
prediccion:
	uv run python -m decla.prediccion.pipeline

# I3 — Fase 11: aplicación Streamlit local de consulta y validación.
app:
	uv run streamlit run src/decla/app/main.py

# Ensambla informe.html a partir de lo que ya calculó `analitica-descriptiva` (hoy son el mismo
# paso: decla.analitica.descriptiva calcula y ensambla en una sola corrida; separar cálculo de
# render queda para cuando el costo de recalcular justifique cachear — ver ADR 0009).
informe: analitica-descriptiva

# Procesa un lote nuevo (I4 — Fase 12): valida esquema, detecta novedades, recalcula lo incremental.
lote:
	uv run python -m decla.ingesta.lote
