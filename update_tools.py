#!/usr/bin/env python3
"""
Viaje a Ítaca — Actualizador autónomo de herramientas IA

Funciona sin intervención humana:
1. Lee el JSON actual de herramientas
2. Consulta fuentes RSS de noticias de IA
3. Busca lanzamientos de nuevas herramientas
4. Si encuentra alguna, la añade al JSON
5. El GitHub Action hace commit automáticamente

Fuentes consultadas (gratuitas, sin API key):
- RSS de TechCrunch AI
- RSS de The Verge AI  
- RSS de VentureBeat AI
- Opcional: Brave Search API, Gemini API (si hay keys configuradas)
"""

import json
import re
import sys
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuración ───────────────────────────────────────────
JSON_PATH = Path(__file__).parent.parent / "herramientas.json"
MIN_FUNCIONES = 3  # Mínimo de funciones para considerar una herramienta válida
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
JSON_PATH = Path(__file__).parent / "herramientas.json"
# RSS feeds gratuitos (sin API key)
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
]

# ─── Utilidades ──────────────────────────────────────────────
def generar_id(nombre):
    """Genera un ID único a partir del nombre"""
    base = re.sub(r'[^a-z0-9]', '-', nombre.lower().strip())
    base = re.sub(r'-+', '-', base).strip('-')
    h = hashlib.md5(nombre.encode()).hexdigest()[:6]
    return f"{base}-{h}" if len(base) > 3 else f"herramienta-{h}"

def es_url_valida(url):
    return url and url.startswith("http")

# ─── Carga de RSS ────────────────────────────────────────────
def fetch_rss():
    """Intenta cargar feedparser; si no está, devuelve [].

    En el entorno de GitHub Actions, feedparser se instala
    automáticamente. Si falla, la ejecución continúa sin RSS.
    """
    try:
        import feedparser
    except ImportError:
        print("⚠️  feedparser no instalado. Instálalo con: pip install feedparser")
        return []

    noticias = []
    for url in RSS_FEEDS:
        try:
            print(f"  📡 Consultando: {url[:60]}...")
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:  # Solo los 15 más recientes
                noticias.append({
                    "titulo": entry.get("title", ""),
                    "resumen": entry.get("summary", entry.get("description", "")),
                    "link": entry.get("link", ""),
                    "fecha": entry.get("published", entry.get("updated", "")),
                    "fuente": url.split("/")[2]
                })
            print(f"     → {len(feed.entries[:15])} entradas")
        except Exception as e:
            print(f"     → Error: {e}")

    print(f"  📰 Total noticias recopiladas: {len(noticias)}")
    return noticias


# ─── Detección de herramientas ───────────────────────────────
# Palabras clave que indican lanzamiento de herramienta IA
PATRONES_LANZAMIENTO = [
    r'(?:lanz[aó]|present[ aó]|anunci[ aó]|debut[ aó]|estren[ aó]|lanza|presenta|anuncia)\s+(?:el|la|su|un|una)?\s*(?:nuev[oa]?\s+)?(?:herramienta|plataforma|asistente|modelo|app|aplicación|servicio)\s+(?:de\s+)?(?:IA|inteligencia\s+artificial)?\s*(?:llamad[oa]?\s+)?[\"«]?([A-ZÁÉÍÓÚ][A-Za-záéíóúÁÉÍÓÚñÑ\s\-\.0-9]{2,40})[\"»]?',
    r'(?:releases?|released|launched?|introduced?|unveiled?|debuts?)\s+(?:the\s+)?(?:new\s+)?(?:AI\s+)?(?:tool|platform|assistant|model|app|service)\s+(?:called\s+)?[\"«]?([A-Z][A-Za-z\s\-\.0-9]{2,40})[\"»]?',
    r'[\"«]([A-Z][A-Za-záéíóúÁÉÍÓÚñÑ\s\-\.0-9]{3,40})[\"»]\s*(?:,?\s*(?:un|una|el|la)\s+)?(?:nuev[oa]\s+)?(?:herramienta|plataforma|asistente|modelo|app|aplicación)\s+(?:de\s+)?(?:IA|inteligencia\s+artificial)',
    r'(?:app|herramienta|plataforma|servicio)\s+(?:de\s+IA\s+)?[\"«]?([A-Z][A-Za-záéíóúÁÉÍÓÚñÑ\s\-\.0-9]{3,40})[\"»]?\s+(?:ha\s+sido\s+)?(?:lanzad[oa]|presentad[oa]|anunciad[oa])',
]

EMPRESAS_CONOCIDAS = {
    "OpenAI": "openai.com",
    "Google": "google.com",
    "Microsoft": "microsoft.com",
    "Meta": "meta.com",
    "Anthropic": "anthropic.com",
    "Amazon": "amazon.com",
    "Apple": "apple.com",
    "Nvidia": "nvidia.com",
    "Adobe": "adobe.com",
    "Canva": "canva.com",
    "Notion": "notion.so",
    "GitHub": "github.com",
    "Stability AI": "stability.ai",
    "Midjourney": "midjourney.com",
    "xAI": "x.ai",
    "Mistral": "mistral.ai",
    "Cohere": "cohere.com",
    "Hugging Face": "huggingface.co",
    "Perplexity": "perplexity.ai",
    "Replit": "replit.com",
    "ElevenLabs": "elevenlabs.io",
    "Runway": "runwayml.com",
    "Suno": "suno.ai",
    "Quora": "quora.com",
}

TIPOS_HERRAMIENTA = {
    "chat": "Chatbot / Asistente",
    "asistente": "Chatbot / Asistente",
    "asistente de código": "Asistente de programación",
    "chatbot": "Chatbot / Asistente",
    "modelo de lenguaje": "Chatbot / Asistente",
    "llm": "Chatbot / Asistente",
    "generador de imágenes": "Generación de imágenes",
    "imagen": "Generación de imágenes",
    "image": "Generación de imágenes",
    "diseño": "Generación de imágenes",
    "vídeo": "Generación de vídeo",
    "video": "Generación de vídeo",
    "música": "Generación de música",
    "audio": "Generación de música",
    "música": "Generación de música",
    "voz": "Síntesis de voz",
    "speech": "Síntesis de voz",
    "código": "Asistente de programación",
    "programación": "Asistente de programación",
    "ide": "IDE con IA",
    "editor": "IDE con IA",
    "buscador": "Buscador / Investigación",
    "búsqueda": "Buscador / Investigación",
    "investigación": "Buscador / Investigación",
    "productividad": "Productividad / Notas",
    "notas": "Productividad / Notas",
    "reuniones": "Productividad / Reuniones",
    "local": "Ejecución local de LLMs",
    "modelo": "Modelo open-source",
}

def detectar_herramientas(noticias):
    """Analiza noticias y extrae nombres de posibles herramientas nuevas"""
    candidatos = []
    textos = []
    for n in noticias:
        texto = (n.get("titulo", "") + " " + n.get("resumen", "")).strip()
        if texto:
            textos.append(texto)

    # Buscar patrones de lanzamiento
    for texto in textos:
        for patron in PATRONES_LANZAMIENTO:
            matches = re.findall(patron, texto, re.IGNORECASE)
            for match in matches:
                nombre = match.strip().strip('"').strip("'").strip("«").strip("»")
                if len(nombre) > 3 and len(nombre) < 50:
                    candidatos.append({
                        "nombre": nombre,
                        "fuente": "RSS (patrón detectado)"
                    })

    # Desduplicar
    vistos = set()
    unicos = []
    for c in candidatos:
        key = c["nombre"].lower()
        if key not in vistos:
            vistos.add(key)
            unicos.append(c)

    print(f"  🔍 Candidatos detectados: {len(unicos)}")
    for c in unicos[:10]:
        print(f"     · {c['nombre']}")

    return unicos


def clasificar_tipo(texto):
    """Intenta clasificar el tipo de herramienta basándose en palabras clave"""
    texto_lower = texto.lower()
    for keyword, tipo in TIPOS_HERRAMIENTA.items():
        if keyword in texto_lower:
            return tipo
    return "Otros"

def detectar_empresa(texto):
    """Intenta detectar la compañía en el texto"""
    for empresa, dominio in EMPRESAS_CONOCIDAS.items():
        if empresa.lower() in texto.lower():
            return empresa
    return "Desconocida"

def crear_herramienta_parcial(candidato, contexto=""):
    """Crea un objeto herramienta con datos parciales (para revisión)"""
    nombre = candidato["nombre"]
    texto = contexto.lower()

    # Determinar si es gratuito/de pago (por defecto asumimos freemium)
    es_gratis = any(w in texto for w in ["gratuito", "gratis", "free", "open-source", "código abierto"])
    es_pago = any(w in texto for w in ["pago", "suscripción", "premium", "plan", "precio", "tarifa", "payment"])

    if es_gratis and not es_pago:
        precio = "Gratuito"
    elif es_pago and not es_gratis:
        precio = "Pago"
    else:
        precio = "Freemium"

    return {
        "id": generar_id(nombre),
        "nombre": nombre,
        "compania": detectar_empresa(contexto),
        "tipo": clasificar_tipo(contexto),
        "precio": precio,
        "gratis": es_gratis or (precio == "Freemium"),
        "pago": es_pago or (precio == "Freemium"),
        "web": "",
        "descripcion": f"Nueva herramienta detectada automáticamente. {contexto[:150]}",
        "funciones": ["Pendiente de revisión"],
        "caracteristicas": ["Detección automática"],
        "etica": "Información pendiente. Herramienta detectada automáticamente.",
        "fecha_agregado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "auto_detectado": True  # Marca para revisión humana opcional
    }


# ─── MAIN ────────────────────────────────────────────────────
def main():
    print("🧭 Viaje a Ítaca — Actualizador autónomo")
    print(f"   Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # Cargar datos actuales
    if not JSON_PATH.exists():
        print("❌ No se encontró herramientas.json")
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        herramientas = json.load(f)

    print(f"📦 Herramientas actuales: {len(herramientas)}")
    ids_existentes = {h["id"] for h in herramientas}
    nombres_existentes = {h["nombre"].lower() for h in herramientas}
    print()

    # ── Paso 1: RSS ──────────────────────────────────────
    print("📡 Buscando noticias de IA...")
    noticias = fetch_rss()
    print()

    # ── Paso 2: Detectar candidatos ──────────────────────
    candidatos = detectar_herramientas(noticias)
    print()

    # ── Paso 3: Filtrar ya existentes ────────────────────
    nuevas = []
    for c in candidatos:
        if c["nombre"].lower() not in nombres_existentes:
            # Buscar contexto en las noticias
            contexto = ""
            for n in noticias:
                if c["nombre"].lower() in (n.get("titulo", "") + n.get("resumen", "")).lower():
                    contexto = (n.get("titulo", "") + " " + n.get("resumen", ""))[:500]
                    break
            h = crear_herramienta_parcial(c, contexto)
            if h["id"] not in ids_existentes:
                nuevas.append(h)

    print(f"✨ Herramientas NUEVAS detectadas: {len(nuevas)}")

    if nuevas:
        for h in nuevas:
            print(f"   🆕 {h['nombre']} [{h['tipo']}] — {h['compania']}")

        herramientas.extend(nuevas)

        # Guardar
        if not DRY_RUN:
            with open(JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(herramientas, f, ensure_ascii=False, indent=2)
            print(f"\n✅ JSON actualizado: {len(herramientas)} herramientas totales.")
        else:
            print(f"\n🔍 DRY RUN: se habrían añadido {len(nuevas)} herramientas.")
    else:
        print("   ℹ️  No se detectaron herramientas nuevas esta semana.")

    # ── Paso 4: Actualizar timestamp ────────────────────
    if herramientas and not DRY_RUN:
        # Buscar si hay version.json para actualizar
        version_path = JSON_PATH.parent / "version.json"
        if version_path.exists():
            with open(version_path, "r", encoding="utf-8") as f:
                version_data = json.load(f)
        else:
            version_data = {}

        version_data["ultima_actualizacion"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        version_data["total_herramientas"] = len(herramientas)

        if not DRY_RUN:
            with open(version_path, "w", encoding="utf-8") as f:
                json.dump(version_data, f, ensure_ascii=False, indent=2)

    print(f"\n🏁 Finalizado. Total: {len(herramientas)} herramientas.")


if __name__ == "__main__":
    main()
