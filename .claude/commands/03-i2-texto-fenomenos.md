---
description: I2 — NLP de RELATO (Fase 4), extracción de conocimiento (Fase 5) y descubrimiento de fenómenos (Fase 6)
---

# I2 — Texto, conocimiento y descubrimiento de fenómenos

Notas adicionales de la persona: $ARGUMENTS

## Contexto
Lee `CLAUDE.md` (§2.3 y §4.15–4.24), `docs/plan_trabajo.md` secciones 6 y 7 y Fases 4, 5, 6 y 10, y el
cierre de I1. Este incremento es el más largo; divídelo en tres bloques con su propia mini-compuerta:
**2A NLP base → 2B menciones y sectores → 2C fenómenos y taxonomía**. Desarrolla y mide todo con los
fixtures sintéticos (tienen verdad de terreno); la evaluación sobre datos reales la hacen analistas con
las herramientas de anotación que construyas.

## Primero: plan
Modo plan para el bloque 2A; al cerrar cada bloque, vuelve a modo plan para el siguiente.

## Bloque 2A — Procesamiento base de RELATO (Fase 4)
1. `texto.relato_procesado`: texto reparado, normalización conservadora (espacios, comillas, guiones,
   palabras partidas), versión en minúscula natural para bloques en mayúsculas sostenidas, sin quitar
   tildes ni números. Toda transformación conserva un mapa de desplazamientos al texto original.
2. **Segmentación de estructura**: reglas para separar `contexto_denuncia` (encabezados de plantilla:
   "siendo las…", "se recibe informe…", "funcionario adscrito a…", "refiere tener conocimiento",
   datos del abogado/defensa, cierre de diligencia) de `descripcion_hecho`. Mide cobertura en fixtures.
3. spaCy `es_core_news_lg` local: oraciones, tokens, lemas, dependencias, NER (PER, ORG, LOC, MISC).
   `EntityRuler` y `PhraseMatcher` con gazetteers en `config/diccionarios/`: instituciones (DIAN, POLFA,
   UIAF, CTI, SIJIN, DIJIN, Fiscalía, Supersociedades, HSI, ICE, CBP, Armada, Ejército, Migración),
   municipios y departamentos DIVIPOLA con desambiguación por contexto, tipos de documento (FPJ-5…).
4. **Patrones por reglas**: artículos penales ("Art. 320 C.P.", "artículo 323"), montos en COP/USD en
   cifras y en letras, fechas y horas (formatos D/M y con mes en texto, tolerando errores tipo
   "AGSOTO"), placas, cédulas (nacional y extranjera), NIT, teléfonos, correos, motor/chasis,
   kilómetros de vía, subpartidas arancelarias.
5. **Enmascaramiento** de datos personales → `[PERSONA]`, `[DOC]`, `[TEL]`, `[CORREO]`, `[PLACA]`,
   `[DIRECCION]`; la versión enmascarada es la única que usan embeddings, vistas y exportes.
   Evalúa exhaustividad en fixtures (objetivo ≥ 0,98 en documentos, teléfonos y correos; ≥ 0,9 en nombres).
6. **Negación, hipótesis y atribución** con reglas tipo NegEx en español ("no se halló", "sin
   encontrar", "presuntamente", "al parecer", "según manifiesta").
7. **Casi-duplicados** con MinHash/LSH + coseno; marca grupos de relatos repetidos.
8. **Embeddings**: fragmentación por oraciones en ventanas que respeten el límite de cada modelo;
   agregación por relato (media y máximo, ambas guardadas) y por segmento `descripcion_hecho`.
   Compara ≥ 2 modelos de `models/MANIFEST.json` (incluido uno de contexto largo) con:
   (a) fixtures (recuperación del fenómeno plantado: precisión@k), y (b) una herramienta local 
   cálculo de Spearman y precisión@k en `reports/agregados/i2/embeddings.md`. Mide tiempo y RAM.
   Guarda vectores en Parquet con `version_modelo`.
9. **Buscador semántico** mínimo (CLI y función reutilizable): consulta en lenguaje natural o
   relato-ejemplo → relatos más similares (texto enmascarado), filtros por año y departamento.

**Mini-compuerta 2A**: modelo de embeddings elegido por mí con base en la comparación.

## Bloque 2B — Menciones y sectores (Fase 5)
1. Tabla `texto.menciones` exactamente con el esquema del plan §6.3 (incluye `texto_evidencia`,
   `inicio`, `fin`, `segmento`, `origen`, `polaridad`, `confianza`, `extractor`, `version_extractor`,
   `estado_revision`).
2. Categorías iniciales en `config/categorias_menciones.yaml` (actividad, mecanismo, bien, sector,
   lugar, fecha, monto, institución, artículo penal, medio de transporte, origen/destino de mercancía),
   con diccionario semilla de vocabulario colombiano por categoría.
3. Clasificación de fragmentos por similitud con definiciones semilla (zero-shot por embeddings) para
   mecanismos y actividades no cubiertos por diccionario, siempre con `origen = inferido_modelo`.
4. **Sectores** (plan §6.4): CIIU Rev. 4 A.C. local; explícito por diccionario de expresiones →
   código; inferido por similitud con descripciones CIIU enriquecidas, top-k con probabilidad
   calibrada; "sector indeterminado" si la confianza o el margen son bajos (umbrales en `config/umbrales.yaml`).
   Nunca vincular sector a persona u organización.
5. **Anotación**: guía `docs/fichas/guia_anotacion.md` (definiciones, casos límite, ejemplos
   sintéticos), configuración de Label Studio local (o un formulario Streamlit si Label Studio no está
   autorizado), selección estratificada + activa (baja confianza primero) de 500–1.500 relatos,
   cálculo de kappa/alfa de Krippendorff y de precisión/exhaustividad por categoría.
6. Si una categoría no alcanza el umbral con reglas, entrena un clasificador multietiqueta (regresión
   logística sobre embeddings; SetFit si hay pocos ejemplos) **solo** con etiquetas aprobadas y partición
   temporal.

**Mini-compuerta 2B**: métricas por categoría publicadas; decido qué categorías alimentan indicadores.

## Bloque 2C — Descubrimiento de fenómenos (Fase 6, plan §7)
1. Pipeline configurable: embeddings de `descripcion_hecho` enmascarada → UMAP (5–15 dims, coseno,
   semilla fija) → HDBSCAN con barrido de `min_cluster_size`/`min_samples` → c-TF-IDF sobre lemas
   (BERTopic con componentes propios). Variante con vector de menciones concatenado.
2. Contrastes: NMF sobre TF-IDF, k-means con k por silueta, aglomerativo para jerarquía.
3. **Estabilidad**: ARI/NMI entre corridas con distinta semilla y submuestras (bootstrap); % ruido.
   En fixtures, medir recuperación de los fenómenos plantados.
4. **Ficha automática por grupo**: términos c-TF-IDF, menciones dominantes con proporción, distribución
   por DELITO, título del CP, unidad, departamento y año (agregada), 5–10 medoides y 3–5 bordes
   (texto enmascarado), indicador de si el grupo está dominado por una sola unidad o plantilla.
5. **Herramienta de revisión** (página Streamlit local) para talleres: aprobar, renombrar, fusionar,
   dividir, marcar artefacto o descartar; prueba de intrusión (5+1 relatos) con registro de aciertos;
   registro de decisiones en `revision.decisiones_taxonomia`.
6. **Taxonomía versionada** en `config/taxonomia/v1.0.yaml` (código estable, nombre, definición,
   inclusión/exclusión, ejemplos sintéticos o ids, nivel jerárquico, delitos relacionados).
7. **Clasificador de fenómenos** multietiqueta sobre la taxonomía aprobada con probabilidad calibrada
   y clase "no clasificado"; tabla `fenomenos.asignacion` (registro_uid, código, probabilidad, método,
   versión). Evaluación con partición temporal.
8. **Conteo de fenómenos** en tres unidades (registros, noticias, grupos conexos), conteo por umbral y
   conteo esperado (suma de probabilidades), y prevalencia ajustada por error de clasificación con
   intervalo. Análisis de robustez del ranking (umbral, modelo, semilla).

## Entregables
`make nlp`, `make conocimiento`, `make fenomenos`; tablas `texto.*` y `fenomenos.*`; buscador
semántico; herramienta de anotación y de revisión; guía de anotación; taxonomía v1.0; fichas de
extractores y del clasificador; `docs/informes/I2_cierre.md`.

## Criterios de aceptación (compuerta I2)
Los del plan Fases 4–6 y la tabla de la sección 9: precisión de reglas ≥ 0,9; kappa ≥ 0,6 en
categorías usadas; intrusión ≥ 80 %; ARI ≥ 0,7 en fenómenos aprobados; ≥ 80 % de la muestra de
validación asignada a un fenómeno que el revisor considera correcto; taxonomía v1.0 aprobada por la
persona responsable.

## No hagas
No leas relatos reales ni pidas que te los peguen; los talleres los hacen analistas en la app local.
No presentes grupos no revisados como fenómenos. No uses metadatos estructurados para formar los
grupos en la primera iteración (solo para describirlos).
