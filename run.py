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
    carpeta = os.path.join(RAIZ, os.environ.get("CARPETA_DATOS", "data"))
    entrada = os.environ.get("ARCHIVO_ENTRADA", "").strip()
    if entrada:
        ruta = entrada if os.path.isabs(entrada) else os.path.join(carpeta, entrada)
    else:
        xs = [x for x in glob.glob(os.path.join(carpeta, "*.xlsx")) if not os.path.basename(x).startswith("~$")]
        if len(xs) != 1:
            sys.exit(f"En {carpeta} debe haber exactamente un .xlsx (hay {len(xs)}), o indique ARCHIVO_ENTRADA en .env")
        ruta = xs[0]
    out = os.path.join(RAIZ, os.environ.get("CARPETA_SALIDA", "out"))
    os.makedirs(out, exist_ok=True)
    nombre = os.path.basename(ruta)
    print(f"Archivo de entrada: {ruta}")

    paso("1/3 Pipeline (territorio, fenómenos, sectores, red, alertas, pronósticos)", ["pipeline/pipeline.py", ruta, out, nombre])
    paso("2/3 Predicciones (genera caso, tiempos de cierre, composición)", ["pipeline/predicciones.py", ruta, out, nombre])
    paso("3/3 Reporte HTML", ["reporte/build_report.py", out, os.path.join(RAIZ, "reporte", "dist", "reporte.html")])

    if "--verificar" in sys.argv:
        paso("Verificación contra el resultado publicado", ["tests/verificar.py", out])
    print("\nListo. Abra reporte/dist/reporte.html en el navegador.")

if __name__ == "__main__":
    main()
