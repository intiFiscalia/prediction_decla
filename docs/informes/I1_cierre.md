# Cierre de I1 — Base confiable e indicadores descriptivos

- **Fecha:** 2026-10-26
- **Corridas de `make etl && make informe` sobre datos reales:** cinco (978 filas de CASOS/RELATOS
  cada vez); las dos primeras expusieron los bugs corregidos abajo, las tres últimas ya reflejan
  las correcciones y son idénticas entre sí en conciliación (978 = 24 + 608 + 346;
  346 noticias = 346 casos = 346 relatos = 632 huérfanos) a través de los `lote_id`
  `5b25657b…`, `4f40d940…` y `d0e27085…`.

## Entregables

- `src/decla/ingesta/bronce.py`, `src/decla/calidad/esquemas.py`: bronce inmutable + validación
  Pandera + cuarentena trazable.
- `src/decla/normalizacion/{identificadores,fechas,codificacion,territorio,coordenadas,delito,
  categoricas,derivados,seudonimizacion,alcance,orquestador}.py`: capa plata completa.
- `src/decla/entidades/{noticia,relato,orquestador}.py`: `noticia_criminal`, `caso`, `grupo_conexo`,
  `relato`/`relato_huerfano`.
- `src/decla/analitica/{indicadores,mapas,descriptiva}.py`: 11 familias de indicadores +
  mapas + matriz origen-destino + informe HTML.
- `src/decla/comun/supresion.py`: supresión de celdas bajas + ocultación de columnas derivadas.
- `docs/fichas/indicadores/` (11 fichas), `data/referencia/{cartografia,poblacion.csv}`.
- 189 pruebas (unitarias + integración), todas contra `tests/fixtures/`; cobertura de
  `decla.normalizacion` **99 %** (umbral de la compuerta: ≥90 %).
- `reports/agregados/i1/`: 12 CSV agregados+suprimidos, 2 mapas PNG, `informe.html`.

## Dos problemas reales encontrados y corregidos durante la revisión

Ambos se detectaron exclusivamente leyendo `reports/agregados/i1/` sobre datos reales — invisibles
en fixtures sintéticos. Ninguno bloqueó la compuerta porque se corrigieron antes de cerrarla.

1. **Fuga de privacidad por supresión secundaria:** `territorio_tasa.csv` publicaba
   `n_registros=<5` pero `tasa_por_100k` sin suprimir; despejando la fórmula
   (`tasa × población / 100.000`) se recuperaba el conteo exacto. El mismo patrón afectaba
   `composicion_delito`, `composicion_estado_etapa`, `territorio_cociente_localizacion`,
   `tiempo_mensual` y `conexidad`. **Corregido** con
   `comun.supresion.ocultar_columnas_derivadas_de_conteo_bajo()`, aplicada antes de la supresión
   normal en las seis tablas afectadas (marcador `"suprimido"`, distinto de `"<5"`).
2. **Métrica de calidad de fechas confundía "ausente" con "inválida":** `calidad.csv` mostraba
   43 % de `CASO_FECHA_PRESCRIPCION` "inválidas" (149/346) y 21,7 % en
   `FECHA_REGISTRO_ACTUACION`/`FECHA_ULTIMA_ACTUACION` (75/346 cada una), muy por encima del 100 %
   válidas que I0 había encontrado sobre las 978 filas completas. La causa no fue el formato de
   fecha (hipótesis inicial descartada tras verificar que el resultado no cambiaba al forzar el
   formato detectado sobre la población completa): el orquestador contaba los valores simplemente
   ausentes (`None`) como "inválidos", mientras que I0 los excluía del denominador. **Corregido**
   separando `fecha_ausente` de `fecha_invalida` (`normalizacion/fechas.py`, nueva categoría
   `fechas_ausentes` en el reporte). Tras el fix, `fechas_invalidas` es 0 en las 8 columnas de
   fecha de CASOS; los 149/75/75/2 casos son datos legítimamente no diligenciados (p. ej. una
   noticia en indagación sin actuaciones posteriores registradas), no un defecto de formato.

También se corrigió un hallazgo menor: `tiempo_mensual.csv` exponía columnas internas de un join
(`_anio_anterior_de`, `mes_right`) sin uso analítico; se eliminan antes de publicar.

## Métricas clave del dataset real (978 filas → 346 en alcance)

| Métrica | Valor |
| --- | --- |
| Conciliación | 978 = 24 cuarentena + 608 fuera de alcance + 346 limpios |
| Alcance excluido | 604 "Delitos Fiscales" + 4 "DFC" (tercer valor de `SECC_DESCRIPCION` no visto en la muestra de I0) |
| Grano tras alcance | 346 = 346 noticias = 346 casos = 346 relatos (1:1, se mantiene) |
| Relatos huérfanos | 632 — **ver nota de alcance abajo**, no son huérfanos "de verdad" en su mayoría |
| Territorio (hechos) | 47,7 % exacto (165), 39,3 % normalizado (136), 13,0 % no resoluble (45) |
| Coordenadas (hechos) | 69,9 % exacta (242), 25,4 % centroide (88), 3,8 % faltante (13), 0,6 % fuera de municipio (2), 0,3 % reparada (1) |
| `DELITO` no parseable | 6,6 % (23/346) |
| Fechas inválidas (tras fix) | 0 % en las 8 columnas |
| Fechas ausentes (tras fix) | `CASO_FECHA_PRESCRIPCION` 43 % (149), `FECHA_REGISTRO_ACTUACION`/`FECHA_ULTIMA_ACTUACION` 21,7 % c/u (75), `FECHA_ASIGNACION` 0,6 % (2), resto 0 % |
| Delito dominante | LAVADO DE ACTIVOS art. 323: 74,3 % (257/346) |
| Estado/etapa dominante | ACTIVO/INDAGACIÓN: 72,0 % (249/346) |
| Conexidad declarada | 1,7 % (6/346) con conexos declarados |
| Rezagos (mediana) | hecho→denuncia 64,5 días; denuncia→creación 0 días; creación→asignación 0 días |
| Unidad que tramita | abrumadoramente concentrada en Bogotá (`cod_dpto_unidad=11`), independiente del departamento de los hechos |

## Nota de alcance sobre `relato_huerfano`

`entidades.relato_huerfano` cuenta 632 relatos sin noticia correspondiente en
`plata.registros_limpios`. Esto **no significa que 632 relatos carezcan de noticia en el dataset
real** (I0 confirmó unión CASOS↔RELATOS perfecta al 100 % sobre las 978 filas): son relatos cuya
noticia existe pero quedó fuera del alcance temático (608 filas de Delitos Fiscales/DFC) o en
cuarentena (24 filas). Es una consecuencia esperada de filtrar por alcance en plata, no un defecto
de la unión. Vale la pena que quede explícito para quien lea `entidades.relato_huerfano` sin este
contexto.

## Confirmación de la persona (2026-10-26)

1. **Concentración territorial de la unidad (confirmada):** la persona confirmó que la
   concentración en Bogotá (`cod_dpto_unidad=11`) es así en la fuente ("así viene la data, nada
   que hacer"); no es un error de mapeo.
2. **Unión CASOS↔RELATOS (verificada a pedido de la persona):** se confirmó en código que
   `entidades/relato.py` cruza `bronce.relatos_raw` contra `plata.registros_limpios` por
   `CASO_NOTICIA`, normalizado con la misma función (`limpiar_identificador`, quita el sufijo
   ".0") en ambos lados — la única columna que comparten los dos documentos fuente. Confirma la
   nota de alcance sobre `relato_huerfano` abajo: la unión no falla, el alcance temático filtra.
3. Rezagos en cero y fechas ausentes altas en prescripción/actuaciones: quedaron documentados
   arriba; la persona no planteó objeciones y pidió continuar el proceso tras revisar una quinta
   corrida idéntica a las anteriores.

## Limitaciones conocidas (no bloquean la compuerta)

- `grupo_conexo` sigue siendo solo un conteo declarado (`NO_CASOS_CONEXOS`), no un grafo real
  (limitación documentada desde el plan de I1).
- Pronósticos (I4) siguen sin ser viables: el dataset real cubre 10 meses de un solo año (2026).
- 45 filas (13,0 % del alcance) con territorio `no_resoluble`: declaradas, no descartadas, pero
  sin resolver.
- `tasa_por_100k`/`tasa_suavizada_por_100k` dependen de `data/referencia/poblacion.csv`; su fuente
  y fecha de corte deben revisarse formalmente en un ADR si se van a usar más allá de I1.

## Compuerta

**Aprobada.** Los tres criterios se cumplen: conteos conciliados (978 = 24 + 608 + 346, idéntico
en las cinco corridas reales) y reejecución idéntica (mismos conteos en `reporte_calidad` a
través de los `lote_id` reales, más prueba de idempotencia en `tests/integracion/
test_idempotencia.py` sobre fixtures); cobertura de pruebas en `decla.normalizacion` del 99 %
(≥90 % exigido); la persona revisó el informe y confirmó la plausibilidad de los conteos
(concentración territorial en Bogotá) y verificó la lógica de unión CASOS↔RELATOS.

**Siguiente paso:** `/03-i2-texto-fenomenos`.
