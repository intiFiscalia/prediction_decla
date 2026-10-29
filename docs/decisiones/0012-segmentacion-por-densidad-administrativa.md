# 0012 — Segmentación contexto_denuncia/descripcion_hecho por densidad administrativa

- **Fecha:** 2026-10-29
- **Estado:** aceptada

## Contexto

Tras revisar `app_revision_fenomenos.py` sobre datos reales, la persona observó que los términos
dominantes de varios grupos eran administrativos ("fecha", "asistencia") en vez de relacionados
con el hecho criminal. El diagnóstico ya estaba documentado (ADR 0010, ADR 0011,
`docs/informes/I2_cierre.md`): la segmentación `contexto_denuncia`/`descripcion_hecho` por frase
exacta (`segmentar`, `config/diccionarios/segmentacion_estructura.yaml`) solo se activaba en
4,9 % de los 346 relatos reales — el resto entra completo (encabezado + hecho) a los embeddings
que alimentan 2B (sector/mecanismo) y 2C (agrupamiento). La persona pidió explícitamente "limpiar
mejor la data y dejar el relato puro del hecho... quitando el encabezado administrativo".

## Decisión

1. **Nuevo método `segmentar_por_densidad`** (`src/decla/texto/segmentacion.py`): en vez de buscar
   frases literales, mide oración por oración (spaCy) la proporción de tokens que pertenecen a
   `config/diccionarios/vocabulario_administrativo.yaml` (72 palabras: marcadores temporales,
   identificación de funcionario/despacho, verbos de trámite/recepción, comparecencia formal,
   conectores de cierre — conocimiento general del dominio, no copiado de relatos reales). La
   primera oración cuya densidad cae por debajo de un umbral marca el inicio de
   `descripcion_hecho`. Si ninguna oración baja del umbral, todo el texto queda como
   `descripcion_hecho` (mismo principio que el método anterior: nunca se inventa un corte sin
   evidencia).
2. **`segmentar_combinado`**: intenta primero la frase exacta (más precisa cuando aparece) y solo
   usa densidad como respaldo si no hay coincidencia literal. Es el método que ahora usa
   `texto/orquestador.py`.
3. **Umbral calibrado empíricamente (`config/umbrales.yaml`, `segmentacion_densidad`) con
   oraciones sintéticas propias, nunca con relatos reales** (CLAUDE.md §2.1): oraciones de hecho
   miden 0,00-0,08 de densidad; 6 de los 8 encabezados sintéticos de
   `scripts/generar_fixtures.py` miden 0,11-0,50. `umbral_densidad = 0.10` separa ambos grupos.
   **Limitación conocida y documentada, no oculta:** 2 estilos de encabezado ("cooperación
   internacional", "control vial") usan redacción genérica sin vocabulario administrativo fuerte
   y miden 0,04-0,05 — el método de densidad no los detecta (si la frase exacta tampoco coincide,
   ese relato queda `sin_marcador`, igual que antes).
4. **Bug encontrado y corregido en `scripts/generar_fixtures.py`:** `construir_relato` armaba el
   texto final muestreando con reemplazo sobre *todas* las oraciones (encabezado + hecho) para
   alcanzar la longitud objetivo, así que el encabezado podía aparecer repetido o fuera de
   posición, no solo al inicio. Esto no refleja la estructura real descrita en CLAUDE.md §4.21
   (el encabezado precede al hecho, no se repite en medio) y hacía que medir cobertura de
   segmentación contra fixtures no fuera representativo del problema real. Corregido: el
   encabezado va una sola vez, siempre de primero; solo las oraciones del hecho se repiten para
   el relleno de longitud.

## Resultado medido (fixtures corregidos, 74 relatos, en primer plano)

| Métrica | Antes (frase exacta, fixtures con bug) | Después (combinado, fixtures corregidos) |
|---|---|---|
| Cobertura segmentación | ~9,5 % (8/84) | **55,4 % (41/74)** |
| Método `marcador_descripcion_hecho` | 8 | 6 |
| Método `densidad_administrativa` | — (no existía) | 35 |
| `precision_recuperacion_fenomeno` (2C) | ~0,25 (ADR 0011) | 0,2222 (umbral de azar: 0,083) |

La cobertura de segmentación mejoró sustancialmente. La recuperación de fenómenos en 2C se
mantiene en el mismo orden de magnitud: la segmentación es una de varias variables que afectan el
agrupamiento (también el modelo de embeddings, hiperparámetros de HDBSCAN, tamaño de muestra), no
la única — consistente con lo ya documentado en ADR 0010/0011. **No se ajustó ningún
hiperparámetro de agrupamiento a ciegas para inflar esta cifra** (CLAUDE.md: "no inventes
cifras").

## Validación sobre datos reales (2026-10-29, 346 relatos en alcance)

La persona corrió `make nlp && make conocimiento && make fenomenos` con el código de esta
decisión y pegó los resultados agregados (nunca texto de relatos):

- **Cobertura de segmentación: 4,9 % (17/346) → 15,0 % (52/346).** Tres veces más, aunque muy por
  debajo del 55,4 % visto en fixtures — los relatos reales tienen más variedad de redacción que
  los 8 estilos sintéticos, confirmando la limitación ya documentada arriba (vocabulario fijo no
  generaliza al 100 %).
- **HDBSCAN pasó de un posible resultado degenerado a 2 grupos reales, 0 % ruido, estabilidad
  perfecta (ARI=NMI=1,0, 10 corridas).** Para descartar que esto fuera un artefacto (ej. mayúsculas
  sostenidas) se corrió `scripts/ver_grupos_descubiertos.py` (consulta agregada de solo lectura
  sobre `fenomenos.grupos_descubiertos`, sin texto de relatos) y se obtuvo:

  | grupo | n_miembros | dominancia_plantilla | dominancia_unidad | términos c-TF-IDF |
  |---|---|---|---|---|
  | 0 | 293 (85 %) | 0,83 | 0,10 | persona, lavado, activo, doc, señor, dinero, delito, policía, identificado, información |
  | 1 | 53 (15 %) | 0,96 | 0,25 | dirección, procedente, judicial, fecha, asistencia, solicitud, oficio, correo, trasladar, activo |

  **Confirma exactamente la hipótesis de ADR 0010/0011, de forma medible:** el agrupamiento separó
  con precisión los relatos donde la segmentación sí funcionó (grupo 0: términos de contenido
  real — lavado, activo, dinero, delito) de los que siguen sin segmentar (grupo 1:
  `dominancia_plantilla = 0,96`, términos puramente administrativos — el mismo patrón "fecha",
  "asistencia" que motivó esta decisión). No es ruido ni un artefacto de mayúsculas: es la
  frontera exacta de cobertura de segmentación, visible en los datos.
- **Decisión de la persona (2026-10-29):** no seguir ajustando segmentación/umbrales ahora. El
  grupo 1 (15 %, boilerplate) se trata en el taller de revisión como candidato a "artefacto de
  plantilla"; el grupo 0 (85 %, con señal de contenido) se revisa normalmente. Se avanza al taller
  de revisión humana con `app_revision_fenomenos.py` sobre este resultado, no se escribe más
  código de segmentación en esta ronda.

## Pendiente

- **Taller de revisión humana** (plan §7.2): analistas usan `app_revision_fenomenos.py` sobre los
  2 grupos reales; grupo 1 es candidato fuerte a "artefacto" por su `dominancia_plantilla` alta.
  Solo después de ese taller se congela `config/taxonomia/v1.0.yaml`.
- Si en una ronda futura se decide exprimir más cobertura de segmentación (no decidido ahora):
  revisar primero por qué los estilos reales no capturados caen por debajo del umbral — candidatos
  documentados arriba son ampliar `config/diccionarios/vocabulario_administrativo.yaml` o bajar
  `umbral_densidad`, nunca tocar hiperparámetros de HDBSCAN primero (mismo orden de prioridad que
  recomendó ADR 0011).
- Reabrir si vale la pena recalcular `embeddings_segmento` vs `embeddings_relato` ahora que
  difieren de verdad para una fracción mayor de relatos (antes eran casi idénticos en 95 % de los
  casos reales, ADR 0005/0010).

## Consecuencias

- `texto/orquestador.py` ahora depende de `config/diccionarios/vocabulario_administrativo.yaml` y
  de `config/umbrales.yaml` (`segmentacion_densidad`) además del diccionario de frases existente.
- `scripts/generar_fixtures.py` cambia la composición exacta de los relatos sintéticos (mismo
  conteo de filas y columnas, misma semilla reproducible); se regeneraron `tests/fixtures/` y los
  356 tests siguen pasando.
- Nuevo `scripts/ver_grupos_descubiertos.py`: utilidad de solo lectura sobre
  `fenomenos.grupos_descubiertos` (tamaño de grupo, indicadores de dominancia, términos c-TF-IDF)
  para que la persona comparta hallazgos agregados sin pegar texto de relatos ni abrir la app de
  revisión cada vez.
