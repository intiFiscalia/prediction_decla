# Manual de la app de consulta (`decla.app.main`)

App Streamlit local, **sin autenticación ni roles** (decisión explícita de la persona, ver ADR
0015): hoy la usa una sola persona en su propia máquina. Abre `data/warehouse.duckdb` en solo
lectura — nunca escribe.

## Cómo correrla

```
make app
```

(equivalente a `uv run streamlit run src/decla/app/main.py`). Requiere que ya hayan corrido, en
este orden, `make etl`, `make nlp`, `make conocimiento`, `make fenomenos`,
`scripts/congelar_taxonomia_v1.py`, `make analitica` y `make emergencia` — cada página lee las
tablas que esos pasos escriben; si falta alguno, la página correspondiente muestra un aviso en
vez de fallar en silencio.

## Páginas

- **Indicadores**: las 13 familias descriptivas (volumen, fenómenos, sectores, delito,
  territorio, tiempo, calidad). Todas declaran su unidad, numerador y limitaciones en
  `docs/fichas/indicadores/`.
- **Fenómenos**: ficha de cada fenómeno aprobado en `config/taxonomia/v1.0.yaml` (términos
  dominantes, dominancia de plantilla, hasta 5 relatos representativos — **siempre
  enmascarados**, no existe un modo de texto original en esta app) y su evolución mensual.
- **Territorio**: perfil territorial por fenómeno, predominio por departamento (con prueba
  binomial frente al segundo y tamaño mínimo), calidad de coordenadas, dispersión de puntos
  válidos, y Moran I bajo demanda (solo se calcula si hay cobertura suficiente; si no, explica
  por qué no).
- **Asociaciones**: cada método se corre bajo demanda (botón), porque algunos son costosos
  (ACM, reglas de asociación). Nunca afirma causalidad — cada resultado trae su propia nota de
  interpretación. El grafo de conexidad no está: `entidades.grupo_conexo` no identifica cuáles
  son los casos conexos (ver ADR 0015).
- **Emergencia**: tabla de `oro.alertas` (candidato_en_observacion / alerta / descartada), de
  solo lectura. Confirmar o descartar una alerta con una persona queda pendiente — necesitaría
  una conexión de escritura separada, como la que ya tiene `app_revision_fenomenos.py` para la
  taxonomía.
- **Buscador semántico**: busca relatos similares a una consulta en lenguaje natural, usando los
  embeddings del lote más reciente en `data/embeddings/`. Si no hay embeddings calculados
  (`make nlp`), lo indica.

## Qué NO hace esta app (alcance deliberadamente reducido, ver ADR 0015)

- No tiene login ni roles — todo el acceso es equivalente a "administrador".
- No tiene bitácora de accesos.
- No permite ver texto de relato sin enmascarar bajo ningún botón o rol.
- No permite confirmar/descartar alertas de emergencia (sí se pueden ver).
- No exporta a Excel/PDF (sí se puede copiar la tabla desde el navegador; CSV vía el menú nativo
  de Streamlit en cada tabla).

Si la herramienta pasa a usarse por más de una persona o se expone fuera de la máquina local, hay
que revisar la decisión de autenticación explícitamente — no es un default que se mantenga
automáticamente si el contexto cambia.
