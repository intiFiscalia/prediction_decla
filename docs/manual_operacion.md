# Manual de operación (I4, Fase 12)

## Procesar un lote nuevo

```
make lote ARCHIVO=/ruta/al/CASOS_nuevo.csv LOTE_ID=<uuid-o-nombre-descriptivo>
```

Esto (`decla.ingesta.lote`):
1. Copia el archivo de forma inmutable a `data/raw/lotes/<LOTE_ID>/` y lo carga a
   `bronce.casos_raw` (reusa `decla.ingesta.bronce.ingerir_tabla`, igual que `make etl`).
2. Valida su esquema contra `config/esquema_fuente.yaml` (las filas sin columna obligatoria van
   a `plata.cuarentena`, nunca se descartan).
3. Clasifica cada fila por `CASO_NOTICIA` frente a todos los lotes anteriores: **nuevo**,
   **repetido** (mismo contenido) o **modificado** (mismo caso, contenido distinto — p. ej.
   `ESTADO`/`ETAPA`/`ULTIMA_ACTUACION` cambiaron). Los cambios quedan en
   `meta.historico_cambios` (campo, valor anterior, valor nuevo, fecha).
4. Calcula deriva (PSI) de volumen, distribución de `DELITO` y de `DEPARTAMENTO_HECHOS` contra
   el histórico. Lectura: PSI < 0,10 sin cambio relevante; 0,10–0,25 cambio moderado; > 0,25
   cambio significativo — revisar antes de confiar en indicadores que mezclen el lote nuevo con
   el histórico sin ajuste.

**Solo procesa CASOS, no RELATOS** (el texto del relato rara vez cambia después de registrado;
si llega un RELATOS nuevo, por ahora se procesa a mano con el mismo criterio que `make etl`).

**Qué `make lote` NO hace automáticamente:** no vuelve a correr `make nlp`, `make conocimiento`,
`make fenomenos`, `make analitica` ni `make emergencia`. Con un solo lote real procesado hasta
ahora no hay base para diseñar bien un recálculo incremental (qué partes de NLP/fenómenos
dependen de qué filas) — es una simplificación deliberada (ver `docs/decisiones/`), no un
olvido. Si el lote nuevo justifica recalcular aguas abajo, correr la cadena completa a mano:

```
make etl && make nlp && make conocimiento && make fenomenos LOTE_ID=<...> \
  && uv run python scripts/congelar_taxonomia_v1.py && make analitica \
  && make emergencia && make prediccion LOTE_ID=<...> && make evaluar
```

## Si la deriva dispara el umbral (PSI > 0,25)

1. Revisar `meta.historico_cambios` y la salida de `make lote` para entender qué cambió (¿un
   departamento nuevo apareció? ¿cambió la proporción de un delito?).
2. Si el cambio es legítimo (p. ej. un nuevo tipo de caso que antes no se registraba), seguir
   adelante y recalcular aguas abajo (ver arriba) — los indicadores reflejarán la realidad nueva.
3. Si el cambio sugiere un error de registro o un cambio de sistema/catálogo (plan_trabajo.md
   §10, riesgo "cambios de procedimientos que crean tendencias falsas"), **no recalcular
   todavía** — confirmar con la persona responsable de datos antes.

## Respaldo cifrado

**Sigue pendiente** (ADR 0007, 2026-10-23): depende de que la oficina jurídica confirme qué
exige sobre retención de bitácoras y reserva sumarial. No se construyó nada nuevo en I4 — ver esa
ADR para las opciones consideradas. Mientras no se resuelva, la única copia de los datos reales
es la que la persona mantenga fuera de este repositorio.

## Rotación de claves de seudonimización

`decla.normalizacion.orquestador.RUTA_CLAVE_HMAC` apunta a la clave usada para seudonimizar
`NUMERO_DOCUMENTO` y `FISCAL_ASIGNADO_DESPACHO` (HMAC). Rotar la clave invalida la
correspondencia entre seudónimos antiguos y nuevos para el mismo valor real — documentar la
fecha de rotación y, si se necesita trazabilidad histórica, conservar la clave anterior en un
lugar seguro fuera del repositorio (nunca en `config/` ni en git).

## Ciclo de revisión de la taxonomía

El plan pide una revisión trimestral con versionado semántico (v1.x para cambios menores, v2.0
cuando cambia el significado de un fenómeno) y una tabla de equivalencias entre versiones. La
taxonomía v1.0 tiene unos días de vida (I2/I3) — no hay nada que versionar todavía. Cuando llegue
el momento: repetir el taller de revisión (`app_revision_fenomenos.py`), decidir si los cambios
son menores (renombrar, ajustar definición → v1.1) o de significado (fusionar/dividir fenómenos
de forma que las series históricas ya no sean comparables → v2.0), y documentar la decisión como
un ADR nuevo con la tabla de equivalencias.

## Ejecuciones programadas

No se usa Prefect/Dagster: con un solo lote real procesado hasta ahora no hay ejecuciones
programadas que lo justifiquen (el plan solo pide esa ADR "si se justifica"). Si en el futuro
hay una cadencia real de lotes, usar `cron` + los targets de este `Makefile` es suficiente para
empezar; reevaluar entonces.

## Registro de modelos

Sin MLflow (no es una dependencia aprobada todavía — añadirla requeriría un ADR). Cada modelo
nuevo tiene su ficha en `docs/fichas/modelos/` (propósito, datos, métricas, limitaciones, usos
no permitidos, responsable) — ver `isolation_forest_atipicos.md` como ejemplo.

## Champion/challenger

No aplica todavía: un solo modelo nuevo (Isolation Forest de atípicos), sin historial de
reentrenamientos que comparar. Documentado, no simulado.

## Guía punto a punto: de datos nuevos al dashboard con fenómenos clasificados (ADR 0024/0025/0027)

Todo lo de ingeniería ya está construido. Lo que sigue sin construirse **a propósito** son los
pasos que exigen criterio humano (anotar, calibrar un umbral con evidencia, decidir si promover
un modelo) — CLAUDE.md §2.3 y §4.6 no permiten que Claude Code los haga, y no hay atajo de
código posible para eso. Esta es la secuencia completa, sin pasos de ingeniería pendientes entre
medio.

### Primera vez (o cuando cambia la taxonomía/el umbral)

```
1.  make etl && make nlp && make conocimiento
2.  make fenomenos LOTE_ID=<el que imprimió make nlp>
3.  uv run streamlit run src/decla/fenomenos/app_revision_fenomenos.py   # taller de taxonomía,
    # si todavía no está congelada v1.0 (ya lo está en este dataset: config/taxonomia/v1.0.yaml)
4.  make analitica    # materializa fenomenos.asignacion_fenomeno con la taxonomía congelada
```

### Anotar y entrenar el clasificador (humano, no tiene atajo)

```
5.  make anotar-fenomenos
    # Anota ≥50-100 relatos por código (plan de muestreo ya estratificado por la app).
    # Doble anotación: repite el muestreo con OTRO calificador (o vos mismo en una pasada
    # ciega, sin ver tus respuestas anteriores) sobre ≥20% de la muestra — es el único paso
    # que la app no puede forzar por sí sola; sin esto, kappa no se puede medir.
    # Casilla "Sugerir con LLM local" (ADR 0026): reemplaza la sugerencia del borrador de
    # clustering por la del modelo Qwen2.5-14B local (más detalle y evidencia citada) — más
    # lento (~30-40s por relato), pero ayuda a llegar al piloto con mejor punto de partida.
    # Sigue siendo el humano quien confirma o corrige; esto no cambia.
6.  Dentro de la app, botón "Calcular resumen agregado":
    - revisa reports/agregados/i4/anotacion_fenomenos.md (cobertura por código, ¿llega a 50?)
    - revisa reports/agregados/i4/candidatos_fenomeno_nuevo.csv (¿hay un término que se repite
      en "otro, especifica"? si sí, es candidato a nuevo fenómeno — decisión aparte, no
      automática)
7.  make clasificar-fenomenos-llm
    # ADR 0027 — el LLM local (Qwen2.5-14B, MLX) clasifica el 100% de los relatos; no hay
    # clasificador rápido filtrando qué revisar (decisión explícita: rigor sobre velocidad).
    # Necesita el modelo descargado antes (`uv run python scripts/descargar_modelos.py --solo
    # qwen2.5-14b-instruct-4bit`, ~8-9GB, una sola vez). Lento por diseño (~38s/relato medidos en
    # Apple M5/16GB): la primera corrida sobre el histórico completo puede tardar horas o días
    # según el volumen real; correrla en background. Las corridas siguientes son incrementales
    # (solo clasifica relatos nuevos) — usar FORZAR=1 solo cuando ajustes el prompt (paso 9) y
    # quieras reclasificar todo de nuevo para medir el efecto.
    # Escribe fenomenos.asignacion_fenomeno_modelo con origen="inferido_modelo_llm".
```

### Evaluar e iterar el prompt (Claude Code lo hace, con la métrica, nunca con el relato)

```
8.  make evaluar-clasificador-llm
    # Compara las predicciones del LLM contra tu anotación confirmada (paso 5) y escribe
    # reports/agregados/i4/clasificador_fenomenos_llm_metricas.md (precisión/exhaustividad/F1
    # por código). Esta es la única cosa que Claude Code lee para decidir si un código necesita
    # mejor prompt — nunca el relato en sí.
9.  Si algún código sale con precisión/exhaustividad baja: pídele a Claude Code que ajuste los
    criterios de "confirmar"/"caso límite" de ese código en
    src/decla/fenomenos/herramienta_anotacion_fenomeno.py:DESCRIPCION_CODIGO (la misma fuente
    que usa el prompt del LLM) y vuelva a correr:
    make clasificar-fenomenos-llm FORZAR=1 && make evaluar-clasificador-llm
    # Repetir hasta que las métricas por código sean aceptables. No hay pesos que entrenar aquí
    # (el modelo se usa por prompting): "reentrenar" es este ciclo de ajustar criterios/ejemplos
    # y volver a medir, no afinamiento de pesos.
```

### Revisar y promover (humano, decisión por código)

```
10. Lee reports/agregados/i4/clasificador_fenomenos_llm_metricas.md. Para cada código: ¿la
    precisión/F1 te convence? Si algún código sale mal, está bien promover solo los que sí
    convencen (o no promover nada todavía y seguir iterando el prompt de ese código).
11. make promover-clasificador-fenomenos VERSION_MODELO=<el que imprimió make clasificar-fenomenos-llm>
    # Copia las filas (solo fenómenos reales de la taxonomía, nunca ruido_administrativo ni
    # no_clasificado) hacia fenomenos.asignacion_fenomeno, con la confianza real del modelo.
```

**Nota sobre el clasificador rápido (sklearn, ADR 0024):** sigue existiendo en el repo
(`make entrenar-clasificador-fenomenos`), pero ya no es parte del camino de producción — la
persona decidió priorizar rigor sobre velocidad (ADR 0027). Queda como código probado, por si en
el futuro se decide usarlo para otra cosa (p. ej. un filtro de primera pasada muy distinto); no
se borró porque no se pidió borrarlo, pero no hay que correrlo para que el flujo de arriba
funcione.

### Ver el resultado en el dashboard

```
12. make emergencia && make prediccion LOTE_ID=<...> && make evaluar
13. make app
```

**Importante — orden que hay que repetir en cada corrida futura:** `make analitica`
reconstruye `fenomenos.asignacion_fenomeno` desde cero (solo clustering). Si volvés a correr
`make analitica` después de promover, el paso 11 (`promover-clasificador-fenomenos`) hay que
repetirlo antes de `make app` — si no, el dashboard vuelve a mostrar solo clustering, sin avisar
con un error (es una tabla que se reconstruye silenciosamente, no un fallo).

### Con un lote de datos nuevo (ya con el prompt validado)

```
make lote ARCHIVO=/ruta/al/CASOS_nuevo.csv LOTE_ID=<nuevo>
make etl && make nlp && make conocimiento && make fenomenos LOTE_ID=<nuevo> && make analitica
make clasificar-fenomenos-llm   # incremental: solo clasifica los relatos del lote nuevo
make promover-clasificador-fenomenos VERSION_MODELO=<el que imprimió el paso anterior>
make emergencia && make prediccion LOTE_ID=<nuevo> && make evaluar && make app
```

La anotación (paso 5) no hay que repetirla desde cero en cada lote: las calificaciones viejas
siguen valiendo (`data/private/anotacion_fenomenos/calificaciones.csv` se acumula). Conviene
anotar una muestra del lote nuevo si cambia mucho la composición (delito, territorio), para que
el reentrenamiento vea ejemplos recientes.
