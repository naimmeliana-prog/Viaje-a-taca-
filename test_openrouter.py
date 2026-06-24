#!/usr/bin/env python3
"""
test_openrouter.py — Diagnóstico de la clave de OpenRouter.
"""
import os, sys, json
import urllib.request, urllib.error

API = "https://openrouter.ai/api/v1"
G = os.environ.get("OPENROUTER_API_KEY", "").strip()
HACER_GENERAR = "--generar" in sys.argv

MODELOS_OBJETIVO = ["meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-lite-preview-02-05:free"]

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {G}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())

def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {G}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://viajeaitaca.es",
        "X-Title": "Viaje a Itaca"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())

def main():
    print("=" * 56)
    print(" DIAGNÓSTICO DE LA CLAVE DE OPENROUTER")
    print("=" * 56)

    if not G:
        print("❌ No hay clave. Define OPENROUTER_API_KEY.")
        sys.exit(1)
    print(f"🔑 Clave detectada (longitud {len(G)}).")

    print("\n[1/2] Verificando clave y modelos disponibles (este endpoint puede no validar la clave al 100% en OpenRouter)...")
    try:
        status, data = get(f"{API}/models")
        print("✅ Endpoint de modelos responde correctamente.")
    except Exception as ex:
        print(f"❌ Error de red: {ex}")
        sys.exit(2)

    if not HACER_GENERAR:
        print("\n[2/2] Prueba de generación OMITIDA.")
        print("      Ejecuta con  --generar  para hacer 1 llamada mínima.")
        return

    modelo = MODELOS_OBJETIVO[0]
    print(f"\n[2/2] Probando generación con {modelo}...")
    payload = {
        "model": modelo,
        "messages": [{"role": "user", "content": "Responde solo: ok"}],
        "temperature": 0.1,
        "max_tokens": 5
    }
    try:
        status, resp = post(f"{API}/chat/completions", payload)
        print(f"✅ Generación correcta (HTTP {status}). La clave genera contenido.")
        print(resp["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"❌ HTTP {e.code} al generar — {body}")
        sys.exit(4)
    except Exception as ex:
        print(f"❌ Error de red al generar: {ex}")
        sys.exit(4)

if __name__ == "__main__":
    main()
