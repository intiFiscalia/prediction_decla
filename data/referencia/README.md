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

Pendiente: cartografía (shapefiles DANE/IGAC para point-in-polygon fino), CIIU Rev. 4 A.C.,
proyecciones de población DANE, catálogo del Código Penal.

Lectura: cualquier colaborador del proyecto, incluido Claude Code.
