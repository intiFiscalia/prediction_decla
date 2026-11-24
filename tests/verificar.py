"""Compara las tablas de out/ con la huella del resultado publicado (tests/referencia.json).
Uso: python3 tests/verificar.py [carpeta_out] [--crear] [--ref ruta_referencia.json]
  --crear  guarda como nueva referencia las huellas actuales (hágalo solo si el cambio fue intencional).
  --ref    usa otra referencia (p. ej. tests/referencia_decla.json); por defecto tests/referencia.json.
La huella es el SHA-256 de las filas en JSON canónico; no incluye el código guardado en "meta".
"""
import sys, os, json, hashlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_args = sys.argv[1:]
if "--ref" in _args:
    i = _args.index("--ref")
    REF = _args[i + 1]
    _args = _args[:i] + _args[i + 2:]
else:
    REF = os.path.join(RAIZ, "tests", "referencia.json")
OUT = next((a for a in _args if not a.startswith("--")), os.path.join(RAIZ, "out"))

def huella(ruta):
    j = json.load(open(ruta, encoding="utf-8"))
    if not isinstance(j, dict) or "rows" not in j:
        return None
    filas = j["rows"]
    return hashlib.sha256(json.dumps(filas, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), len(filas)

actual = {f: huella(os.path.join(OUT, f)) for f in sorted(os.listdir(OUT)) if f.endswith(".json") and not f.startswith("ia_")}
actual = {f: h for f, h in actual.items() if h}
# En modo IA la sección 10 usa la clasificación del modelo; se verifica la copia por reglas guardada aparte.
for base_ in ("la_fenomenos", "la_meta"):
    if f"{base_}_reglas.json" in actual:
        actual[f"{base_}.json"] = actual.pop(f"{base_}_reglas.json")
        print(f"(modo IA: se verifica {base_}_reglas.json, el resultado por reglas)")
for extra in ("ia_comparacion.json",):
    actual.pop(extra, None)
if "--crear" in sys.argv:
    json.dump({f: {"sha256": h, "filas": n} for f, (h, n) in actual.items()}, open(REF, "w"), indent=1)
    print(f"Referencia guardada con {len(actual)} tablas."); sys.exit(0)

ref = json.load(open(REF))
mal = 0
for f, r in ref.items():
    if f not in actual:
        print(f"FALTA     {f}"); mal += 1
    elif actual[f][0] != r["sha256"]:
        print(f"DISTINTO  {f}  ({actual[f][1]} filas; referencia {r['filas']})"); mal += 1
    else:
        print(f"igual     {f}  ({r['filas']} filas)")
if mal:
    sys.exit(f"\n{mal} tabla(s) no coinciden con el resultado publicado. Si cambió el Excel de entrada, es lo esperado.")
print(f"\nLas {len(ref)} tablas coinciden exactamente con el resultado publicado.")
