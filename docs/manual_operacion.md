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
