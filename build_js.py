#!/usr/bin/env python3
"""
Regenera data/herramientas.js a partir de herramientas.json.

Solo reemplaza el array de datos embebidos (var herramientasIA = [ ... ];).
NO toca la configuración (URLs, intervalo) ni la lógica de auto-actualización,
de modo que el cargador sigue intacto y los datos quedan sincronizados con el JSON.
"""
import json, re, sys
from pathlib import Path

raiz = Path(__file__).parent
JSON = raiz / "herramientas.json"
JS   = raiz / "data" / "herramientas.js"

if not JSON.exists():
    print("::error::no existe herramientas.json"); sys.exit(1)
if not JS.exists():
    print("::error::no existe data/herramientas.js"); sys.exit(1)

with open(JSON, encoding="utf-8") as f:
    datos = json.load(f)
# Las herramientas de prueba nunca van al archivo público.
datos = [h for h in datos if not h.get("es_prueba")]

js = JS.read_text(encoding="utf-8")

# Serializa cada herramienta en una línea (formato compacto, como el original).
lineas = []
for h in datos:
    lineas.append("  " + json.dumps(h, ensure_ascii=False, separators=(",", ":")) + ",")
bloque = "var herramientasIA = [\n" + "\n".join(lineas) + "\n];"

patron = re.compile(r"var herramientasIA = \[[\s\S]*?\n\];")
if not patron.search(js):
    print("::error::no se encontró el array herramientasIA en data/herramientas.js"); sys.exit(1)

nuevo = patron.sub(lambda m: bloque, js, count=1)

if nuevo != js:
    JS.write_text(nuevo, encoding="utf-8")
    print(f"data/herramientas.js regenerado con {len(datos)} herramientas.")
else:
    print(f"data/herramientas.js sin cambios ({len(datos)} herramientas).")
