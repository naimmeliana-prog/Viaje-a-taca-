#!/usr/bin/env python3
"""
test_gemini.py — Diagnóstico de la clave de Gemini (secret ITACA).

Comprueba, gastando lo MÍNIMO de cuota:
  1. Que la clave existe y es válida.
  2. Qué modelos puede usar tu clave (no consume cuota de generación).
  3. (Opcional) Una micro-llamada de 1 token para confirmar que genera.

Uso local:
    GEMINI_API_KEY="tu_clave" python3 test_gemini.py
    GEMINI_API_KEY="tu_clave" python3 test_gemini.py --generar   # hace 1 llamada mínima

En GitHub Actions se ejecuta con el secret ITACA (ver workflow test-gemini.yml).
No imprime la clave en ningún momento.
"""
import os, sys, json
import urllib.request, urllib.error

API = "https://generativelanguage.googleapis.com/v1beta"
G = os.environ.get("GEMINI_API_KEY", "").strip()
HACER_GENERAR = "--generar" in sys.argv

# Modelos que usa update_tools.py, en su orden de preferencia.
MODELOS_OBJETIVO = ["gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]


def get(url):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def main():
    print("=" * 56)
    print(" DIAGNÓSTICO DE LA CLAVE DE GEMINI (ITACA)")
    print("=" * 56)

    if not G:
        print("❌ No hay clave. Define GEMINI_API_KEY (o el secret ITACA).")
        sys.exit(1)
    print(f"🔑 Clave detectada (longitud {len(G)}, no se muestra por seguridad).")

    # ── 1) Listar modelos: valida la clave SIN gastar cuota de generación ──
    print("\n[1/2] Verificando clave y modelos disponibles...")
    try:
        status, data = get(f"{API}/models?key={G}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        if e.code == 400:
            print(f"❌ HTTP 400 — clave mal formada o inválida.\n   {body}")
        elif e.code == 403:
            print(f"❌ HTTP 403 — clave inválida/revocada o API no habilitada.\n   {body}")
        elif e.code == 429:
            print(f"⚠️  HTTP 429 — la clave es VÁLIDA pero sin cuota ahora mismo.\n   {body}")
        else:
            print(f"❌ HTTP {e.code} — {body}")
        sys.exit(2)
    except Exception as ex:
        print(f"❌ Error de red: {ex}")
        sys.exit(2)

    disponibles = []
    for m in data.get("models", []):
        nombre = m.get("name", "").replace("models/", "")
        metodos = m.get("supportedGenerationMethods", [])
        if "generateContent" in metodos:
            disponibles.append(nombre)

    print(f"✅ Clave VÁLIDA. {len(disponibles)} modelos con generateContent.")

    print("\n   Modelos que usa el catálogo:")
    alguno_ok = False
    for m in MODELOS_OBJETIVO:
        ok = m in disponibles
        alguno_ok = alguno_ok or ok
        print(f"     {'✅' if ok else '❌'} {m}")
    if not alguno_ok:
        print("\n   ⚠️ Ninguno de los modelos del catálogo está disponible.")
        print("      Edita MODELOS en update_tools.py con uno de estos:")
        for m in disponibles[:12]:
            print(f"        - {m}")

    # ── 2) (Opcional) micro-llamada de generación ──
    if not HACER_GENERAR:
        print("\n[2/2] Prueba de generación OMITIDA (no gasta cuota).")
        print("      Ejecuta con  --generar  para hacer 1 llamada mínima.")
        print("\n🧭 Resultado: clave OK. Lista para usarse en el workflow.")
        return

    modelo = next((m for m in MODELOS_OBJETIVO if m in disponibles), None) or (disponibles[0] if disponibles else None)
    if not modelo:
        print("\n[2/2] No hay modelo disponible para probar generación.")
        sys.exit(3)

    print(f"\n[2/2] Probando generación con {modelo} (1 token, mínimo gasto)...")
    payload = {
        "contents": [{"parts": [{"text": "Responde solo: ok"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
    }
    try:
        status, resp = post(f"{API}/models/{modelo}:generateContent?key={G}", payload)
        print(f"✅ Generación correcta (HTTP {status}). La clave genera contenido.")
        print("\n🧭 Resultado: clave OK y operativa. Todo listo.")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        if e.code == 429:
            print(f"⚠️  HTTP 429 — clave válida pero cuota agotada. Reintenta tras el reinicio diario.\n   {body}")
            sys.exit(4)
        print(f"❌ HTTP {e.code} al generar — {body}")
        sys.exit(4)
    except Exception as ex:
        print(f"❌ Error de red al generar: {ex}")
        sys.exit(4)


if __name__ == "__main__":
    main()
