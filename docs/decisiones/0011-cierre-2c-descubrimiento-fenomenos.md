# 0011 — Cierre del Bloque 2C: descubrimiento de fenómenos

- **Fecha:** 2026-10-28
- **Estado:** aceptada — mini-compuerta 2C cerrada **parcialmente** (lo que no depende del
  taller de revisión humana); taxonomía v1.0, clasificador y conteo quedan explícitamente
  pendientes de ese taller, no de más código.

## Contexto

Bloque 2C (plan_trabajo.md §7, Fase 6) construye: representación vectorial (embeddings de
`descripcion_hecho_enmascarada` + vector de menciones), reducción UMAP, agrupamiento (HDBSCAN
principal + 3 contrastes: k-means, NMF, aglomerativo — alcance completo confirmado por la
persona, 2026-10-28), selección por estabilidad (ARI/NMI entre bootstraps), ficha automática por
grupo, y la herramienta de revisión (Streamlit) para el taller con analistas.

## Bug real encontrado y corregido durante el desarrollo

Al medir sobre fixtures, la primera corrida dio `n_grupos_hdbscan=0`: la selección por
estabilidad elegía sistemáticamente una configuración donde **todo el agrupamiento era ruido**
(todas las etiquetas `-1`). Causa: una partición constante (todo en una sola clase, incluido
"todo ruido") obtiene ARI/NMI = 1.0 trivialmente entre corridas de bootstrap, porque nunca varía
— eso le permite "ganar" la selección por estabilidad sin aportar ninguna estructura real.
**Corregido** en `_seleccionar_hdbscan_por_estabilidad` (`src/decla/fenomenos/orquestador.py`):
se descartan los candidatos con menos de 2 grupos reales (sin contar ruido) antes de competir por
estabilidad, con una salida de emergencia documentada si el barrido completo resultara
degenerado (no crashea, deja estabilidad en 0 visible). Tras el fix, HDBSCAN encuentra grupos
reales sobre fixtures y sobre los parámetros por defecto de `config/fenomenos.yaml`.

## Resultado sobre fixtures (84 relatos, verdad de terreno de 12 fenómenos plantados)

`precision_recuperacion_fenomeno` (proporción del fenómeno plantado mayoritario dentro de cada
grupo, ponderada por tamaño) salió claramente por encima del azar (1/12 ≈ 0,083) pero **baja en
términos absolutos** (ver `tests/integracion/test_fenomenos_orquestador.py`,
`test_recuperacion_de_fenomeno_plantado_supera_el_azar` — la prueba exige solo superar el azar,
no un umbral de calidad alto). Esto **confirma empíricamente** el riesgo ya documentado en
ADR 0010 y anticipado por plan_trabajo.md §7 ("grupos que reflejan la plantilla de la unidad que
redacta, no el fenómeno"): con solo 4,9 % de los relatos reales con `contexto_denuncia` separado,
el vector de entrada sigue dominado por lenguaje compartido entre relatos de fenómenos distintos.

**No se intenta "arreglar" esto ajustando hiperparámetros a ciegas** (CLAUDE.md: "no inventes
cifras"): es exactamente el problema que el taller de revisión humana (fusionar, dividir, marcar
artefacto) está diseñado para corregir, y que mejorar la segmentación `contexto_denuncia`/
`descripcion_hecho` (ADR 0005) aliviaría en la raíz. Ambos quedan como trabajo futuro, no como
bloqueante de este cierre.

## Qué se cierra y qué no

**Cerrado y probado (código, no requiere taller):**
- `representacion.py`, `reduccion.py`, `agrupamiento.py` (4 métodos), `estabilidad.py`,
  `ficha_grupo.py`, `orquestador.py`/`pipeline.py` (`make fenomenos`).
- `herramienta_revision.py` + `app_revision_fenomenos.py`: funcional, probada contra datos
  sintéticos reales del pipeline (no solo mocks), incluida la prueba de intrusión.
- `config/taxonomia/v0.1-borrador.yaml`: generado automáticamente, con el estado
  `pendiente_revision` en cada grupo — nunca se presenta como fenómenos validados.

**Explícitamente pendiente (no es código, es trabajo de taller con analistas):**
- **Taxonomía v1.0** (`config/taxonomia/v1.0.yaml`): solo existe después de que analistas
  revisen los grupos con `app_revision_fenomenos.py` y aprueben/fusionen/dividan/descarten.
- **Clasificador multietiqueta** (`fenomenos.asignacion`, plan §7.3): se entrena solo con
  ejemplos de la taxonomía aprobada. Interfaz esperada cuando se construya: tabla
  `fenomenos.asignacion(registro_uid, codigo_fenomeno, probabilidad, metodo, version_taxonomia)`,
  con clase `"no_clasificado"` para probabilidad bajo umbral, y partición temporal para evaluar
  (nunca aleatoria, CLAUDE.md §2.3).
- **Conteo con incertidumbre** (plan §7.4): tres unidades (registros, noticias, grupos conexos),
  conteo por umbral y conteo esperado (suma de probabilidades), prevalencia ajustada por error de
  clasificación con intervalo. Depende enteramente del clasificador anterior.

## Consecuencias

- No se avanza a I3 (que usa la taxonomía aprobada como insumo) hasta que el taller ocurra y se
  registre su resultado en un ADR nuevo.
- Si el taller revela que la mayoría de los grupos son artefactos de plantilla (confirmando la
  hipótesis de ADR 0010), la prioridad antes de reintentar el agrupamiento debería ser mejorar
  `config/diccionarios/segmentacion_estructura.yaml` con frases reales que un analista identifique
  al leer una muestra — no volver a tunear umbrales de HDBSCAN sin ese insumo.
