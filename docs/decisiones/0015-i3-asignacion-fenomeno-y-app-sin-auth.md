# 0015 — I3: `fenomenos.asignacion_fenomeno` y app sin autenticación/roles

- **Fecha:** 2026-11-04
- **Estado:** aceptada

## Contexto

Al planear I3 (análisis relacional, territorio, emergencia, app — plan_trabajo.md Fase 7-8-11)
se encontraron dos huecos reales entre lo que el plan define como artefacto y lo que el código
tenía construido hasta el cierre de I2, más una decisión explícita de alcance de la persona sobre
la app.

### Hueco 1 — no existía `fenomenos.asignacion_fenomeno`

El plan (Fase 4) define `asignacion_fenomeno` (registro, fenómeno, probabilidad, método) como el
artefacto limpio que articula indicadores, territorio, asociaciones y emergencia. Lo que existía
era solo `fenomenos.grupo_asignacion_borrador` (una fila por relato **y método de clustering**) y
`config/taxonomia/v1.0.yaml` (los códigos aprobados), pero el YAML congelado no guardaba a qué
`grupo_id`/`metodo` de origen correspondía cada código — `construir_taxonomia_v1` usaba `grupo_id`
solo como clave interna del bucle, nunca lo persistía.

### Hueco 2 — `entidades.grupo_conexo` no identifica casos conexos

La tarea de asociaciones (plan §8.3) pide un "grafo de conexidad... si I0 confirmó cómo se
identifican los conexos". I0/I1 nunca lo confirmaron: `grupo_conexo` es solo el conteo declarado
`NO_CASOS_CONEXOS` (documentado en `I1_cierre.md`), 1,7 % de los registros con conexos declarados
en el dataset real. No hay con qué construir un grafo real.

### Decisión de alcance — app sin autenticación ni roles

La Fase 11 del plan pide 4 roles (consulta/analista/revisor/administrador) con
streamlit-authenticator o proxy institucional. La persona decidió explícitamente simplificar: hoy
la herramienta la usa una sola persona en su propia máquina, nada se expone a la web, y lo que
importa es el resultado analítico, no el control de acceso ("no me interesa que sea lindo o
segura para la web, todo esto es local").

## Decisión

1. **`taxonomia_v1.py` ahora persiste `grupo_id_origen`/`metodo_origen`** en cada fenómeno
   aprobado (se calculaban como clave del bucle, solo faltaba guardarlos). `decla.fenomenos.
   asignacion.construir_asignacion_fenomeno` los usa para filtrar `grupo_asignacion_borrador` y
   escribir `fenomenos.asignacion_fenomeno` (probabilidad fija en 1.0 — es membresía de
   clustering, Fase 6, no de un clasificador calibrado, eso es Fase 9/I4).
2. **Un mismo relato puede quedar bajo más de un código.** Dos de los cuatro fenómenos de v1.0
   vienen de la partición de HDBSCAN (`lavado_de_activos`) y dos de la partición de NMF
   (`lavado_de_activos_a_traves_de_empresas`, `incautacion_y_conteo_de_efectivo`,
   `organizacion_criminal` — tres, no dos); cada partición cubre el 100 % del corpus con grupos
   disjuntos *entre sí*, pero un relato puede caer en un grupo aprobado de HDBSCAN y en un grupo
   aprobado distinto de NMF a la vez. No es multietiqueta genuino (eso exigiría que el mismo
   método detectara dos fenómenos en un relato); es un efecto de mezclar dos particiones para
   construir la taxonomía. Documentado en el código (`asignacion.py`) y en la ficha de
   `ind_fenomenos`: la suma de `n_noticias` por fenómeno puede superar el total de relatos, y eso
   es esperado.
3. **Grafo de conexidad: explícitamente no construido.** Documentado en
   `decla.analitica.asociaciones` y en este ADR — no se simula con datos que no están.
4. **App sin autenticación ni roles.** `decla.app.main` no tiene login ni diferenciación de
   roles; todas las vistas asumen acceso total (equivalente a "administrador"). Se mantiene sin
   cambios lo que protege a terceros en los datos (supresión de celdas bajas en exportes,
   enmascaramiento de relatos — nunca existe un modo "texto original" en esta app), porque eso
   no es parte de la autenticación que se está simplificando, es parte de la corrección del
   resultado. La cola de revisión de alertas (confirmar/descartar) queda pendiente de una
   conexión de escritura separada, como ya existe para la taxonomía (`app_revision_fenomenos.py`)
   — no se construye esta ronda.

## Consecuencias

- `config/taxonomia/v1.0.yaml` necesita volver a congelarse (`scripts/congelar_taxonomia_v1.py`,
  lo corre la persona) para que los 4 fenómenos ya aprobados ganen `grupo_id_origen`/
  `metodo_origen` — sin eso, `construir_asignacion_fenomeno` los omite explícitamente (no inventa
  la trazabilidad que falta).
- Si en el futuro se construye el clasificador multietiqueta genuino (Fase 9/I4), probabilidad en
  `asignacion_fenomeno` dejará de ser 1.0 fijo — el esquema de la tabla ya lo admite.
- Si la herramienta pasa a usarse por más de una persona o se expone fuera de la máquina local,
  hay que revisar esta decisión de autenticación explícitamente — no es un default que se
  mantenga "porque sí" si el contexto cambia.
- El grafo de conexidad sigue pendiente de un hallazgo de datos (cómo se identifican los conexos)
  que no depende de este incremento.
