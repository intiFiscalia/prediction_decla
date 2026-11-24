"""Ejecuta todo el proyecto: Excel de data/ -> tablas en out/ -> reporte/dist/reporte.html.

    python run.py              # procesa y arma el reporte
    python run.py --verificar  # además compara out/ con tests/referencia.json (resultado publicado)

Configuración en .env (copie .env.example). Sin .env usa los valores por defecto.
"""
import os, sys, glob, subprocess, json

RAIZ = os.path.dirname(os.path.abspath(__file__))

def cargar_env(ruta):
    """Lector mínimo de .env (CLAVE=valor), sin dependencias. Sus valores reemplazan a los del entorno."""
    if not os.path.exists(ruta):
        return
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")  # el .env manda sobre variables ya definidas en el equipo

def paso(nombre, args):
    print(f"\n== {nombre}")
    r = subprocess.run([sys.executable, "-I", *args], cwd=RAIZ)
    if r.returncode:
        sys.exit(f"Falló: {nombre}")

def main():
    cargar_env(os.path.join(RAIZ, ".env"))
    fuente = "gic"
    if "--fuente" in sys.argv:
        fuente = sys.argv[sys.argv.index("--fuente") + 1].strip().lower()
    if fuente not in ("gic", "decla"):
        sys.exit(f"--fuente debe ser 'gic' o 'decla' (recibido: {fuente})")

    carpeta = os.path.join(RAIZ, os.environ.get("CARPETA_DATOS", "data"), "GIC" if fuente == "gic" else "DECLA")
    entrada = os.environ.get("ARCHIVO_ENTRADA", "").strip()
    if entrada:
        ruta = entrada if os.path.isabs(entrada) else os.path.join(carpeta, entrada)
    else:
        xs = [x for x in glob.glob(os.path.join(carpeta, "*.xlsx")) if not os.path.basename(x).startswith("~$")]
        if len(xs) != 1:
            sys.exit(f"En {carpeta} debe haber exactamente un .xlsx (hay {len(xs)}), o indique ARCHIVO_ENTRADA en .env")
        ruta = xs[0]
    out = os.path.join(RAIZ, os.environ.get("CARPETA_SALIDA", "out"), fuente)
    os.makedirs(out, exist_ok=True)
    nombre = os.path.basename(ruta)
    dest = os.path.join(RAIZ, "reporte", "dist", f"reporte_{fuente}.html")
    print(f"Fuente: {fuente}  ·  Archivo de entrada: {ruta}")

    if fuente == "gic":
        paso("1/3 Pipeline (territorio, fenómenos, sectores, red, alertas, pronósticos)", ["pipeline/pipeline.py", ruta, out, nombre])
        paso("2/3 Predicciones (genera caso, tiempos de cierre, composición)", ["pipeline/predicciones.py", ruta, out, nombre])
    else:
        paso("1/3 Pipeline DECLA (territorio, fenómenos, sectores, red, alertas, pronósticos)", ["pipeline/pipeline_decla.py", ruta, out, nombre])
        paso("2/3 Predicciones DECLA (composición de fenómenos)", ["pipeline/predicciones_decla.py", ruta, out, nombre])
    paso("3/3 Reporte HTML", ["reporte/build_report.py", out, dest, fuente])

    if "--verificar" in sys.argv:
        ref = os.path.join(RAIZ, "tests", "referencia.json" if fuente == "gic" else "referencia_decla.json")
        paso("Verificación contra el resultado publicado", ["tests/verificar.py", out, "--ref", ref])
    print(f"\nListo. Abra {dest} en el navegador.")

if __name__ == "__main__":
    main()
