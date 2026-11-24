# GIC · Reporte de fenómenos criminales

Convierte los Excel de relatos/casos de la Fiscalía en reportes de 8 secciones (indicadores, fenómenos,
territorio, sectores, red, alertas, predicciones y organizaciones), idénticos al tablero publicado en Claude.
Hay **dos fuentes independientes**, cada una con su propio Excel, su propia carpeta de salida y su propio HTML:

| Fuente  | Excel de entrada                              | Salida JSON | Reporte HTML                          |
|---------|------------------------------------------------|-------------|----------------------------------------|
| `gic`   | `data/GIC/DatosAn_lisisReumenGICLavado_V1.xlsx`| `out/gic/`  | `reporte/dist/reporte_gic.html`        |
| `decla` | `data/DECLA/DECLA_2024_2026.xlsx`              | `out/decla/`| `reporte/dist/reporte_decla.html`      |

> Todas las cifras miden **actividad institucional registrada** (relatos o casos que llegaron a la Fiscalía), no
> la incidencia real del delito.

## ⚠️ `python run.py` sin `--fuente` SOLO genera GIC

`run.py` por defecto usa `--fuente gic` (compatibilidad con invocaciones antiguas). Para tener los dos reportes
hay que correrlo **dos veces**, una por fuente:

```bash
python run.py --fuente gic   --verificar
python run.py --fuente decla --verificar
```

Si solo corre `python run.py` a secas, no se toca ni se borra `reporte/dist/reporte_decla.html`: simplemente no
se regenera, y puede quedar desactualizado respecto al Excel de DECLA sin que nada avise. No hay un comando
"generar todo"; si quiere las dos fuentes siempre, encadénelos con `&&` o un script propio.

## Requisitos

- Python 3.13 (probado con 3.13). Otras versiones 3.11+ funcionan, pero para obtener *exactamente* las mismas cifras
  use las versiones fijadas en `requirements.txt`.
- Un navegador moderno para abrir el reporte.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (cmd.exe):**

```bat
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

> En macOS/Linux el comando suele ser `python3`; en Windows, `py` o `python`. El resto de comandos de este README
> (`python run.py ...`) funciona igual en los tres entornos una vez activado el entorno virtual (`.venv`); si su
> `python` no apunta a Python 3, use `python3` (Mac/Linux) o `py` (Windows) en su lugar.

## Uso

1. Cada fuente tiene su propia carpeta: ponga el Excel de GIC en `data/GIC/` y el de DECLA en `data/DECLA/`. Cada
   carpeta debe tener **exactamente un** `.xlsx`; si hay varios, indique cuál usar con `ARCHIVO_ENTRADA` en `.env`
   (se aplica a la fuente que esté corriendo en ese momento).
2. Revise `.env` (incluido). `.env.example` es la plantilla sin secretos. Sus valores reemplazan a las variables de
   entorno del equipo con el mismo nombre.
3. Ejecute, **una vez por cada fuente que necesite**:

```bash
python run.py --fuente gic                # procesa GIC y arma reporte_gic.html
python run.py --fuente gic   --verificar  # además confirma que el resultado es idéntico al publicado

python run.py --fuente decla               # procesa DECLA y arma reporte_decla.html
python run.py --fuente decla --verificar   # además confirma que el resultado es idéntico al publicado

python run.py                              # equivale a --fuente gic (valor por defecto); NO corre decla
```

4. Abra `reporte/dist/reporte_gic.html` y/o `reporte/dist/reporte_decla.html`.

### ¿Da el mismo resultado?

Sí, para el mismo Excel. `--verificar` compara las tablas generadas en `out/<fuente>/` contra la huella del
resultado publicado para esa fuente y debe terminar con:

```
Las 22 tablas coinciden exactamente con el resultado publicado.      # --fuente gic
Las 15 tablas coinciden exactamente con el resultado publicado.      # --fuente decla
```

Todo el proceso es determinista: semillas fijas, relatos/casos ordenados por fecha e Id antes de analizar (el
orden de las filas del Excel no importa), sin llamadas a servicios externos. Si cambia el Excel de una fuente,
`--verificar` mostrará tablas `DISTINTO` en esa fuente (la otra fuente no se ve afectada): es lo esperado. Si el
cambio es intencional y quiere fijarlo como nueva referencia:

```bash
python tests/verificar.py out/gic --crear                               # nueva referencia de GIC
python tests/verificar.py out/decla --ref tests/referencia_decla.json --crear   # nueva referencia de DECLA
```

El Excel de GIC debe tener las mismas columnas que el original (49), en especial `ResumenHechos`,
`TematicaPriorizada`, `LugarDeLosHechos`, `FechaIngreso`, `FechaRecepcionAjust`, `FechaCierreAjust`,
`DecisionFiscalUGIC`, `ETAPA`, `DELITO`, `GrupoEstructura`, `Estructura`, `EntidadRemite` e `IdEntrada`.

El Excel de DECLA debe tener las hojas `Hoja1` (casos SPOA, 40 columnas: `ESTADO`, `ETAPA`, `DELITO`, `CAPITULO`,
`TITULO`, `DEPARTAMENTO_HECHOS`, `MUNICIPIO_HECHOS`, `COMPETENCIA_DESPACHO`, `TIPO_NOTICIA`, `TIPO_DILIGENCIA`,
`CASO_FECHA_DENUNCIA`, `FECHA_CREACION`, `FECHA_HECHO`, `CASO_NOTICIA`, etc.) y `Relato` (`CASO_NOTICIA`,
`RELATO`), unidas 1 a 1 por `CASO_NOTICIA`. DECLA no tiene campos de trámite/entrada (`TipoEntrada`,
`EntidadRemite`, `CanalRecepción`, `DecisionFiscalUGIC`): las piezas del reporte que dependen de eso se omiten
con una nota «No aplica» en vez de inventar un sustituto.

## Estructura

```
data/
  GIC/                    Excel de entrada de GIC (datos personales: manéjelo según su política)
  DECLA/                  Excel de entrada de DECLA (datos personales: manéjelo según su política)
pipeline/
  pipeline.py             GIC: bronce→plata→entidades→fenómenos→oro: territorio DIVIPOLA, taxonomía, sectores
                          CIIU, asociaciones (Fisher + Benjamini–Hochberg), red, alertas EARS/CUSUM, pronósticos
  predicciones.py         GIC: probabilidad de generar caso, tiempo hasta el cierre (Kaplan–Meier), composición
  pipeline_decla.py       DECLA: mismo tipo de pipeline que pipeline.py pero sobre casos SPOA ya abiertos;
                          nunca importa ni modifica pipeline.py
  predicciones_decla.py   DECLA: composición de fenómenos (las piezas que no aplican a DECLA se omiten);
                          nunca importa ni modifica predicciones.py
  taxonomia.py            taxonomía versionada de fenómenos, mecanismos, bienes, sectores y organizaciones
                          (compartida por las dos fuentes; cambiarla afecta a ambas)
  divipola.py             departamentos y municipios DIVIPOLA (con coordenadas de cabeceras; compartido)
assets/dptos_geo.json     límites departamentales simplificados (MGN DANE 2018)
reporte/
  src/                    código de la página (el mismo del tablero publicado; común a las dos fuentes)
  dash_shim.js            entorno local que reemplaza al del tablero de Claude
  vendor/d3.v7.min.js     d3 v7 (licencia ISC)
  build_report.py         arma reporte/dist/reporte_<fuente>.html con todo incrustado
tests/
  verificar.py            compara out/<fuente> con la referencia de esa fuente
  referencia.json         huellas del resultado publicado de GIC (22 tablas)
  referencia_decla.json   huellas del resultado publicado de DECLA (15 tablas)
  probar_reporte.mjs      prueba un HTML en un navegador simulado (Node + jsdom); recibe la ruta del reporte
out/
  gic/                    tablas generadas de GIC (JSON); cada una lleva su código en "meta"
  decla/                  tablas generadas de DECLA (JSON); cada una lleva su código en "meta"
```

## Textos fijos que dependen de los datos

Algunas frases del reporte describen la base actual y no se recalculan solas (están en `reporte/src/index.html`):
el nombre del archivo y el rango de fechas en «Fuente, método y limitaciones», el vacío de registro de
jul–ago 2025, los meses completos, la fecha de corte y cifras como el «79 % en indagación». Si cambia de base
(en cualquiera de las dos fuentes), revíselas.

## Probar el HTML (opcional)

```bash
npm install jsdom
node tests/probar_reporte.mjs reporte/dist/reporte_gic.html     # 0 errores, ningún «—» sin llenar
node tests/probar_reporte.mjs reporte/dist/reporte_decla.html   # 0 errores; "No aplica"/"No disponible para
                                                                  # esta fuente" son el resultado esperado en
                                                                  # las piezas omitidas para DECLA, no un «—»
```

Debe abrir las 8 pestañas y terminar con `errores: 0 []` en cada reporte.
