# data/embeddings/

Vectores de `texto.embeddings_relato`/`texto.embeddings_segmento`, en Parquet, versionados por
`version_modelo` (plan_trabajo.md §6.1 paso 9). Se calculan siempre sobre `relato_enmascarado`
(nunca sobre el texto original con datos personales): no es información reservada, pero se
regenera con `make nlp` y no se versiona en git por su tamaño.

Estructura: `<lote_id>/relato.parquet`, `<lote_id>/segmento.parquet`.

Lectura: cualquier colaborador del proyecto, incluido Claude Code.
