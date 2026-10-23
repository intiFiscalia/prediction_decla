# data/referencia/

Fuentes públicas descargadas previamente a la red local: DIVIPOLA (DANE), cartografía municipal
(DANE/IGAC), CIIU Rev. 4 A.C., proyecciones de población DANE, catálogo del Código Penal. No son
datos del caso ni contienen información reservada.

## Contenido

- `divipola.csv` (2026-10-23): códigos y nombres de departamento/municipio con centroide
  (`cod_dpto`, `cod_mpio`, `departamento`, `municipio`, `lat_centroide`, `long_centroide`),
  1122 municipios. Fuente: dataset oficial DANE "DIVIPOLA- Códigos municipios" publicado en
  datos.gov.co (Socrata, `gdxc-w37w`), exportado vía
  `https://www.datos.gov.co/resource/gdxc-w37w.csv`. Revisar vigencia antes de usarlo en un
  informe oficial: DANE puede actualizar el dataset (nuevos municipios, cambios de nombre).

- `poblacion.csv` (2026-10-23): población total proyectada por municipio y año
  (`cod_dpto`, `cod_mpio`, `departamento`, `municipio`, `anio`, `poblacion_total`), años 2018–2042,
  1122 municipios por año (solo fila "Total" de área geográfica; se descartan los desgloses
  cabecera/rural). Fuente: DANE, "Proyecciones de población municipal por área 2018-2042" (CNPV
  2018), archivo oficial
  `https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx`.

- `cartografia/municipios.geojson` y `cartografia/departamentos.geojson` (2026-10-23): polígonos
  simplificados a escala nacional, con código DIVIPOLA en `divipola_mun`/`divipola_dep`
  (coinciden con `cod_mpio`/`cod_dpto` de `divipola.csv`). Fuente: obra derivada del Marco
  Geoestadístico Nacional 2025 (DANE), simplificada por
  [ytolosa/mapas-colombia](https://github.com/ytolosa/mapas-colombia) bajo **CC BY 4.0** — usar
  requiere citar: "Cartografía: Marco Geoestadístico Nacional 2025, DANE. Simplificación:
  github.com/ytolosa/mapas-colombia, CC BY 4.0." No usar para catastro oficial ni análisis
  espacial de alta precisión (es una simplificación); para eso, los shapefiles originales del
  [geoportal del DANE](https://geoportal.dane.gov.co/).

Pendiente: CIIU Rev. 4 A.C., catálogo del Código Penal.

Lectura: cualquier colaborador del proyecto, incluido Claude Code.
