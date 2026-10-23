---
description: I0 — Diagnóstico de datos (Fase 1) y cierre de la arquitectura local (Fase 2)
---

# I0 — Diagnóstico y arquitectura (Fases 1 y 2 del plan)

Notas adicionales de la persona: $ARGUMENTS

## Contexto
Lee `CLAUDE.md` (en especial §2.1 y §4) y `docs/plan_trabajo.md` Fases 1 y 2. El objetivo es conocer
la composición real del dataset completo y fijar la unidad de análisis **antes** de cualquier modelo.
Recuerda: tú escribes el diagnóstico y lo pruebas con fixtures; yo lo ejecuto con `make diagnostico`
sobre los datos reales y tú solo lees `reports/agregados/diagnostico/`.

## Primero: plan
Modo plan. Propón tareas, salidas esperadas y criterios; espera aprobación.

## Tareas
1. **Lector de fuentes** (`src/decla/ingesta/lectores.py`): `.numbers`, `.xlsx`, `.csv` (detección de
   separador y codificación), todo como texto, ignora filas totalmente vacías y las cuenta, conserva el
   número de fila original. Devuelve un objeto con tabla, nombre de hoja/tabla, conteos y advertencias.
2. **Contrato de esquema** (`config/esquema_fuente.yaml` + validador): columnas esperadas de CASOS y
   RELATOS, alias, obligatoriedad. Informe: columnas faltantes, nuevas, renombradas, tipos observados
   (numérico, fecha, texto, mixto) y % vacío. Contrasta con el inventario de 28 campos del plan y
   con las 40 columnas observadas en la muestra.
3. **Perfil de calidad** (`src/decla/calidad/diagnostico.py`) que produzca, en agregado:
   - Cardinalidad de `CASO_ID`, `CASO_NOTICIA` y del par; duplicados exactos; duplicados parciales
     (misma noticia con distinto DELITO, DESPACHO, FECHA_ASIGNACION, ULTIMA_ACTUACION) para inferir
     qué representa una fila. Propón 2–3 hipótesis de grano con evidencia numérica.
   - Unión CASOS↔RELATOS: cobertura en ambos sentidos, relatos por noticia (distribución), huérfanos.
   - Verificación de la hipótesis de estructura de `CASO_NOTICIA` (21 dígitos): % que cumple longitud,
     % cuyo prefijo DANE existe en DIVIPOLA, % cuyo año embebido coincide con el año de
     `CASO_FECHA_REG_NC`/`FECHA_CREACION`, % cuyo municipio embebido coincide con municipio de hechos o
     de unidad.
   - Fechas: formato detectado por columna, % inválidas, rango, distribución por mes, % futuras,
     violaciones de orden lógico (hecho ≤ denuncia ≤ creación/registro ≤ asignación; última actuación
     ≥ creación), % donde prescripción = hecho + 20 años (y desvíos).
   - Faltantes por columna × año × departamento (¿no aleatorios?).
   - Territorio: valores únicos de departamento/municipio (hechos y unidad), % que casa exacto con
     DIVIPOLA, % que casa tras normalización, % por coincidencia difusa (con umbral), % no resoluble.
     Para no exponer valores reales, el informe de no resolubles lista solo conteos; la lista completa
     queda en `data/private/` para revisión humana.
   - Coordenadas: % vacías, % válidas en caja de Colombia, % reparables por reescalado decimal,
     % invertidas, % que caen en el municipio declarado (tras reparación), % coincidentes con centroide.
   - Categóricas: catálogo y frecuencias de ESTADO, ETAPA, TIPO_NOTICIA, TIPO_DILIGENCIA,
     COMPETENCIA_DESPACHO, TITULO, CAPITULO, DELITO (separado en nombre/artículo/cuantía),
     ULTIMA_ACTUACION, `Eje temático APLICA`, SECC_DESCRIPCION, LEY. Proporción de art. 323 vs. otros
     delitos (fuente/conexos). Valores con frecuencia < 5 se agrupan como "otros (<5)".
   - Relatos: longitud en caracteres/palabras/tokens estimados (percentiles), % vacíos, % con mojibake
     cirílico y % reparado sin residuo, % en mayúsculas sostenidas, relatos idénticos o casi idénticos
     (MinHash) entre noticias distintas, indicios de truncamiento (longitudes repetidas en un máximo),
     % con patrones de datos personales (cédula, teléfono, correo, placa) — solo conteos.
   - Estabilidad temporal: volumen mensual por fecha de registro, aparición/desaparición de categorías,
     puntos de cambio (ruptures) que sugieran cambios de sistema o práctica.
   - Periodo cubierto y número de meses con datos: decide si I4 (pronósticos) es viable.
4. **Muestra para lectura humana**: genera en `data/private/muestra_lectura/` una muestra
   estratificada de 300 relatos (año, departamento, delito, longitud) en un HTML local con el texto
   reparado y enmascarado, y un formulario simple (CSV) para que analistas anoten fenómeno, mecanismo y
   sector. No la leas tú.
5. **Informe** `reports/agregados/diagnostico/informe.md` + tablas CSV agregadas con supresión < 5,
   y gráficos PNG sin texto de relatos.
6. **Arquitectura (Fase 2)**: con los volúmenes del informe, completa `docs/decisiones/` con:
   unidad de análisis (propuesta para mi aprobación), DuckDB vs. PostgreSQL, granularidad temporal
   (semana/mes/trimestre), modelo de embeddings candidato según longitud de relatos y hardware,
   orquestación (Makefile vs. Prefect), y plan de respaldo cifrado.
7. Pruebas con fixtures que demuestren que cada métrica del diagnóstico detecta los defectos plantados
   (comparando con `tests/fixtures/verdad.parquet`).

## Entregables
`make diagnostico`, informe agregado, matriz de calidad por columna, diccionario de datos ampliado
(`docs/fichas/diccionario_datos.md`: inventario + hallazgos), tabla de mapeo territorial propuesta,
registro de supuestos, ADRs de arquitectura.

## Criterios de aceptación (compuerta I0)
- Grano de la tabla explicado con evidencia y **aprobado por mí**.
- 100 % de valores territoriales mapeados o marcados "no resoluble".
- Reglas de fechas inválidas definidas en `config/reglas_fechas.yaml`.
- Perfil de RELATO publicado; regla de reparación de codificación validada.
- Decisión sobre viabilidad de pronósticos según el periodo real.

## No hagas
No limpies ni transformes datos todavía (eso es I1). No leas `data/raw/` ni `data/private/`.
No entrenes modelos.

## Al terminar
Cuando yo te confirme que ejecuté `make diagnostico`, lee el informe agregado, resume los 10 hallazgos
más importantes, actualiza `CLAUDE.md` §4 y §6, y hazme las preguntas de la compuerta con opciones
concretas (grano, unidad de análisis, umbrales de fecha, tratamiento de huérfanos, `Eje temático APLICA`).
