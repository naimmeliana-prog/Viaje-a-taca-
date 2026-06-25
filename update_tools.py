import json,re,sys,hashlib,os
from datetime import datetime,timezone
from pathlib import Path

# Frases "vacías" que algunos modelos devuelven en vez de un dato real.
_NO_DATO={"no especificado","no especificada","desconocido","desconocida","n/a","na","none","null","sin especificar","-",""}
def url_valida(v):
 if not isinstance(v,str) or not v.strip().lower().startswith(("http://","https://")) or v.strip().lower() in _NO_DATO:
  return False
 # Blacklist de dominios marcados recurrentemente por phising o dominios genéricos peligrosos
 blacklist = [".zip", "onbrand.slidespeak.co"]
 return not any(b in v.lower() for b in blacklist)

def enlace_vivo(url):
 """Comprueba si una web existe y NO es un dominio en venta/aparcado.
 Mantiene la tolerancia a Cloudflare (si da error HTTP asume que está viva)."""
 import socket as _sock, ssl as _ssl
 import urllib.request as _u
 from urllib.parse import urlparse as _up
 if not url_valida(url):return False
 host=_up(url).hostname or ""
 try:
  _sock.gethostbyname(host)
 except Exception:
  return False # No hay DNS, web muerta
  
 _ctx=_ssl.create_default_context()
 _ctx.check_hostname=False
 _ctx.verify_mode=_ssl.CERT_NONE
 try:
  req=_u.Request(url, headers={"User-Agent":"Mozilla/5.0"})
  with _u.urlopen(req, timeout=8, context=_ctx) as r:
   # Si responde bien, leemos el contenido para cazar cybersquatters
   html = r.read(8192).decode("utf-8", errors="ignore").lower()
   toxicos = ["domain is for sale", "buy this domain", "godaddy", "hugedomains", "sedo.com", "domain has expired", "this page is parked", "inquire about this domain", "afternic", "window.location.href=\"/lander\""]
   if any(t in html for t in toxicos):
    return False # Es una web de venta de dominios
   
   # Comprobar redirecciones meta y javascript de aparcamiento
   if "/lander" in html or "parking-page" in html:
    return False
 except _u.HTTPError as e:
  if e.code in (404, 410):
   return False # Si es un 404 real (como un repo de Github borrado), la damos por muerta
  return True # Resto de HTTP Errors (403, 503) los damos por vivos para no asustarnos con Cloudflare
 except Exception:
  pass # Timeouts... lo perdonamos
 return True




J=Path(__file__).parent/"herramientas.json"
G=os.environ.get("OPENROUTER_API_KEY","")
MODO_PRUEBA=os.environ.get("MODO_PRUEBA","")=="1"

# Modelos a probar en orden. Se puede forzar uno con la variable OPENROUTER_MODEL.
# Los *-lite suelen tener cuota gratuita más generosa (menos errores 429).
_modelo_env=os.environ.get("OPENROUTER_MODEL","").strip()
MODELOS=[_modelo_env] if _modelo_env else [
 "openrouter/free"
]
REINTENTOS=8          # intentos por modelo ante un 429
ESPERA_BASE=8         # segundos; los modelos gratuitos de openrouter se colapsan a ratos

# Anotaciones visibles en GitHub Actions (salen resaltadas en rojo/amarillo)
def err(m):print("::error::"+m)
def warn(m):print("::warning::"+m)

if not J.exists():err("no existe herramientas.json");sys.exit(1)
with open(J) as f:t=json.load(f)
t=[h for h in t if not h.get("es_prueba")]
print(f"Actuales: {len(t)}")

# ─────────────────────────────────────────────────────────────
# 0) AUDITORÍA AUTÓNOMA: Limpieza de duplicados y URLs tóxicas
# ─────────────────────────────────────────────────────────────
_nombres_vistos = set()
_t_limpio = []
_duplicados = 0
_webs_toxicas = 0

# Señales de que una URL es un aparcamiento de dominios o un placeholder genérico
DOMINIOS_TOXICOS = ["godaddy.com", "domainname.com", "hugingface.co", "github.com/None", "example.com", "tbd.com", "comingsoon.com", "example.org", "test.com"]

for h in t:
    # a) Purgador de duplicados por similitud (fuzzy match)
    nm = h.get("nombre", "").lower().replace(" ", "").replace("-", "").replace("‑", "").replace("—", "")
    
    if nm in _nombres_vistos:
        _duplicados += 1
        continue
        
    encontrado = False
    for visto in _nombres_vistos:
        # Excepciones lógicas de la misma suite (ej. stt vs s2s)
        if "stt" in nm and "s2s" in visto: continue
        if "s2s" in nm and "stt" in visto: continue
        
        # Purgado difuso de versiones (ej: glm vs glm5.2)
        # Si comparten los primeros 4 caracteres y la diferencia son números, lo consideramos el mismo producto
        # o si uno está contenido en el otro (con límite menor para nombres cortos)
        if (len(nm) > 3 and len(visto) > 3) and (nm in visto or visto in nm):
            _duplicados += 1
            encontrado = True
            break
            
    if encontrado: continue
    
    _nombres_vistos.add(nm)
    
    # b) Auditor de URLs tóxicas / alucinadas
    web_actual = h.get("web", "")
    if web_actual:
        if any(toxico in web_actual.lower() for toxico in DOMINIOS_TOXICOS) or not enlace_vivo(web_actual):
            # Si era la única que teníamos y es tóxica, probamos a volver al provisional o la dejamos vacía
            prov = h.get("li") or h.get("enlace")
            h["web"] = prov if prov else ""
            h.pop("intentos_web", None) # Resetea la cola
            _webs_toxicas += 1
        
    _t_limpio.append(h)

if _duplicados or _webs_toxicas:
    t = _t_limpio
    print(f"Auditoría automática: {_duplicados} duplicados purgados, {_webs_toxicas} URLs tóxicas reseteadas.")

ids={h["id"] for h in t}
nombres=[h["nombre"] for h in t]

# ─────────────────────────────────────────────────────────────
# MODO PRUEBA: añade una herramienta falsa para verificar el flujo
# ─────────────────────────────────────────────────────────────
if MODO_PRUEBA:
    fake={
        "id":"test-herramienta-"+datetime.now(timezone.utc).strftime("%Y%m%d%H%M"),
        "nombre":"Herramienta de Prueba "+datetime.now(timezone.utc).strftime("%d/%m %H:%M"),
        "compania":"Viaje a Itaca (prueba)",
        "tipo":"Chatbot / Asistente",
        "precio":"Gratuito",
        "gratis":True,
        "pago":False,
        "web":"https://viajeaitaca.great-site.net",
        "descripcion":"Herramienta de prueba. Confirma que el sistema funciona.",
        "funciones":["Verificar funcionamiento","Modo prueba"],
        "caracteristicas":["Generada por el sistema","Se elimina al siguiente ciclo sin prueba"],
        "etica":"Herramienta de prueba. Sin implicaciones eticas.",
        "fecha_agregado":datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "auto_detectado":True,
        "es_prueba":True
    }
    t=[h for h in t if not h.get("es_prueba")]
    t.append(fake)
    with open(J,"w",encoding="utf-8") as f:json.dump(t,f,ensure_ascii=False,indent=2)
    print(f"MODO PRUEBA: anadida herramienta falsa. Total: {len(t)}")
    print(f"   Nombre: {fake['nombre']}")
    sys.exit(0)

# ─────────────────────────────────────────────────────────────
# 1) Recoger titulares de los feeds RSS
# ─────────────────────────────────────────────────────────────
try:
 import feedparser
 n=[]
 for u in [
  # --- Medios IA generalistas (verificados, funcionan) ---
  "https://techcrunch.com/category/artificial-intelligence/feed/",
  "https://venturebeat.com/category/ai/feed/",
  "https://www.artificialintelligence-news.com/feed/",
  "https://www.theregister.com/software/ai_ml/headlines.atom",
  "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
  "https://arstechnica.com/ai/feed/",
  "https://www.wired.com/feed/tag/ai/latest/rss",
  "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
  "https://www.technologyreview.com/feed/",
  "https://www.newscientist.com/subject/artificial-intelligence/feed/",
  "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
  # --- Lanzamientos de productos/herramientas (añadidos y verificados 2026-06-20) ---
  "https://www.producthunt.com/feed?category=artificial-intelligence",  # productos nuevos a diario
  "https://www.marktechpost.com/feed/",                                  # lanzamientos y releases
  "https://the-decoder.com/feed/",                                       # productos y modelos nuevos
  "https://dailyai.com/feed/",                                           # herramientas y noticias IA
  "https://syncedreview.com/feed/",                                      # nuevos modelos/sistemas
  "https://huggingface.co/blog/feed.xml",                                # modelos y librerías open-source
  "https://hnrss.org/newest?q=AI+tool",                                  # "AI tool" en Hacker News
  "https://hnrss.org/newest?q=launch+AI",                                # lanzamientos en Hacker News
 ]:
  try:
   f=feedparser.parse(u)
   # Product Hunt = lanzamientos de productos: cogemos más entradas de ahí.
   tope=25 if "producthunt" in u else 15
   medio=(f.feed.get("title","") or "")[:40]
   for e in f.entries[:tope]:
    fp=e.get("published_parsed") or e.get("updated_parsed")
    iso=""
    if fp:
     try:
      from time import strftime
      iso=strftime("%Y-%m-%dT%H:%M:%SZ",fp)
     except:pass
    n.append({"ti":e.get("title",""),"re":re.sub(r"<[^>]+>","",e.get("summary",e.get("description",""))),"li":e.get("link",""),"fuente":u,"medio":medio,"fecha":iso})
  except:pass
 print(f"Noticias: {len(n)}")
except:
 n=[];warn("feedparser no disponible: sin RSS")

if not n:
 warn("0 noticias recogidas de los feeds RSS (¿feeds caídos o red bloqueada?)")

# ─────────────────────────────────────────────────────────────
# 1b) Generar noticias.json para la barra lateral de la web.
#     Clasifica en "novedades" (todas) y "etica" (filtradas por palabras clave).
# ─────────────────────────────────────────────────────────────
def _guardar_noticias(items):
 N=Path(__file__).parent/"noticias.json"
 # Feeds en ESPAÑOL dedicados a la barra de noticias (verificados).
 # Feeds en español para NOVEDADES de IA (verificados).
 FEEDS_NOV=[
  ("https://www.xataka.com/tag/inteligencia-artificial/rss2.xml","Xataka"),
  ("https://www.genbeta.com/tag/inteligencia-artificial/rss2.xml","Genbeta"),
  ("https://www.applesfera.com/tag/inteligencia-artificial/rss2.xml","Applesfera"),
  ("https://www.xatakandroid.com/tag/inteligencia-artificial/rss2.xml","Xataka Android"),
  ("https://wwwhatsnew.com/tag/inteligencia-artificial/feed/","WWWhat's new"),
  ("https://planetachatbot.com/feed/","Planeta Chatbot"),
  ("https://www.computing.es/inteligencia-artificial/feed/","Computing.es"),
  ("https://blogthinkbig.com/feed","Think Big")
 ]
 # Feeds en español dedicados a ÉTICA / regulación / privacidad (verificados).
 FEEDS_ETI=[
  ("https://www.xataka.com/tag/etica/rss2.xml","Xataka"),
  ("https://www.xataka.com/tag/regulacion/rss2.xml","Xataka"),
  ("https://wwwhatsnew.com/tag/etica/feed/","WWWhat's new"),
  ("https://blogthinkbig.com/tag/etica/feed","Think Big"),
  ("https://www.genbeta.com/tag/privacidad/rss2.xml","Genbeta"),
  ("https://derechodelared.com/feed/","Derecho de la Red")
 ]
 def _bajar(feeds):
  out=[]
  try:
   import feedparser as _fp
   from time import strftime
   for u,medio in feeds:
    try:
     f=_fp.parse(u)
     for e in f.entries[:12]:
      fp=e.get("published_parsed") or e.get("updated_parsed")
      iso=""
      if fp:
       try:iso=strftime("%Y-%m-%dT%H:%M:%SZ",fp)
       except:pass
      out.append({"ti":e.get("title",""),"re":re.sub(r"<[^>]+>","",e.get("summary",e.get("description",""))),"li":e.get("link",""),"medio":medio,"fecha":iso})
    except:pass
  except:pass
  return out
 nov=_bajar(FEEDS_NOV)
 eti=_bajar(FEEDS_ETI)
 # Filtrar que las de ética sean realmente de IA (no tecnología genérica).
 def es_ia(it):
  tx=((it.get("ti") or "")+" "+(it.get("re") or "")).lower()
  return any(k in tx for k in [" ia ","inteligencia artificial","chatgpt","gemini",
   "claude","algoritmo","chatbot","openai"," llm","machine learning","deep learning",
   "modelo de ia","modelos de ia","modelo de lenguaje","generativa","deepfake",
   "anthropic","copilot","redes neuronales","aprendizaje automático"])
 eti=[x for x in eti if es_ia(x)]
 nov=[x for x in nov if es_ia(x)] # ¡Aseguramos que La Vanguardia y otros no cuelen cosas de Nintendo!
 # Añadir también ética RECIENTE detectada en los feeds de novedades
 # (los feeds de etiqueta ética se actualizan despacio).
 KW_ETI_TIT=["ética","etica","ético","etico","sesgo","privacid","regulac","regula",
  "prohib","deepfake","vigilancia","desinformación","desinformacion","derechos de autor",
  "copyright","demanda","gobernanza","ley de ia","ai act","censura","datos personales",
  "propiedad intelectual","manipula","fraude","estafa","dilema"]
 for x in nov:
  t=(x.get("ti") or "").lower()
  if any(k in t for k in KW_ETI_TIT):
   eti.append(x)
 print(f"Noticias ES: {len(nov)} novedades, {len(eti)} de ética")
 def limpio(it):
  return {
   "titulo":(it.get("ti") or "").strip()[:160],
   "resumen":re.sub(r"\s+"," ",(it.get("re") or "")).strip()[:220],
   "enlace":it.get("li",""),
   "medio":it.get("medio","") or "",
   "fecha":it.get("fecha","") or ""
  }
 def dedup(lst):
  vis=set();out=[]
  for x in lst:
   t=x["titulo"].lower()
   if t and t not in vis:
    vis.add(t);out.append(x)
  return out
 # Si no hubo feeds en español (red caída), caer a lo recogido antes.
 if not nov and not eti:
  nov=items; eti=items
 novedades=dedup([limpio(x) for x in sorted(nov,key=lambda it:it.get("fecha",""),reverse=True) if (x.get("ti") or "").strip()])[:30]
 etica=dedup([limpio(x) for x in sorted(eti,key=lambda it:it.get("fecha",""),reverse=True) if (x.get("ti") or "").strip()])[:20]
 data={
  "actualizado":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "novedades":novedades,
  "etica":etica
 }
 with open(N,"w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
 print(f"noticias.json: {len(novedades)} novedades, {len(etica)} de ética")

if n:
 _guardar_noticias(n)

c=[]
ia_ok=False

# ─────────────────────────────────────────────────────────────
# 2) Análisis con IA OpenRouter (fuente principal de detección)
# ─────────────────────────────────────────────────────────────
def llamar_ia(prompt):
 """(Adaptado a OpenRouter) Devuelve (texto, True) si responde 200. Recorre MODELOS y reintenta."""
 import time
 import requests as rq
 cuota=False
 for modelo in MODELOS:
  url="https://openrouter.ai/api/v1/chat/completions"
  headers = {
      "Authorization": f"Bearer {G}",
      "Content-Type": "application/json",
      "HTTP-Referer": "https://viajeaitaca.es",
      "X-Title": "Viaje a Itaca"
  }
  payload = {
      "model": modelo,
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.1
  }
  for intento in range(1,REINTENTOS+1):
   try:
    rp=rq.post(url, headers=headers, json=payload, timeout=40)
   except Exception as ex:
    warn(f"[{modelo}] error de red (intento {intento}): {ex}")
    time.sleep(ESPERA_BASE)
    continue
   if rp.status_code==200:
    print(f"✓ IA OK con modelo {modelo}")
    try:
     js = rp.json()
     if "choices" in js: return js["choices"][0]["message"]["content"],True
     elif "candidates" in js: return js["candidates"][0]["content"]["parts"][0]["text"],True # Fallback just in case openrouter passes native gemini format
     else: raise Exception("No choices or candidates found in response")
    except Exception as ex:
     warn(f"[{modelo}] respuesta 200 pero ilegible: {ex} - {rp.text[:150]}")
     return None,True
   if rp.status_code==429:
    cuota=True
    if intento<REINTENTOS:
     espera=ESPERA_BASE*intento
     warn(f"[{modelo}] cuota agotada (429). Reintento {intento}/{REINTENTOS-1} en {espera}s...")
     time.sleep(espera)
     continue
   else:
    warn(f"[{modelo}] HTTP {rp.status_code}: {rp.text[:100]}")
    break
 if cuota:warn("Cuota de IA agotada (HTTP 429) en todos los reintentos.")
 return None,False

if not G:
 warn("Falta el secret OPENROUTER_API_KEY (ITACA). Se usará solo la heurística, mucho menos fiable.")
elif n:
 print("🤖 IA OpenRouter analizando (modelos: "+", ".join(MODELOS)+")...")
 # Muestra repartida entre fuentes (round-robin) para que IA no vea
 # solo los primeros feeds. Product Hunt primero (es donde hay herramientas).
 def _muestra(items, limite=60):
  porfuente={}
  for it in items:
   porfuente.setdefault(it.get("fuente",""),[]).append(it)
  fuentes=sorted(porfuente, key=lambda u: 0 if "producthunt" in u else 1)
  out=[]; i=0
  while len(out)<limite and any(porfuente.values()):
   for u in fuentes:
    if porfuente[u]:
     out.append(porfuente[u].pop(0))
     if len(out)>=limite: break
   i+=1
   if i>200: break
  return out
 muestra=_muestra(n,60)
 hdr="\n".join([x["ti"]+" — "+x["re"][:160] for x in muestra])
 known=", ".join(nombres[:50])
 p=(
  "Eres un analista de herramientas de IA para un catálogo en español. "
  "A partir de estos titulares, identifica SOLO herramientas/productos de IA NUEVOS y reales "
  "(no funciones de productos ya conocidos). YA CONOCIDAS (ignóralas): "+known+"\n\n"
  "TITULARES:\n"+hdr+"\n\n"
  "Devuelve SOLO un array JSON. Cada objeto con estos campos en español: "
  "nombre, compania, tipo, precio (uno de: Gratuito, Freemium, Pago), descripcion (1-2 frases), "
  "web, funciones (array de 3-6), caracteristicas (array de 3-6), "
  "etica (1-2 frases sobre privacidad/sesgos/impacto). "
  "Si no hay ninguna herramienta nueva clara, devuelve []."
 )
 tx,ia_ok=llamar_ia(p)
 if tx:
  # Limpiar bloques markdown si la IA los devuelve
  tx_clean = tx.replace("```json", "").replace("```", "").strip()
  m=re.search(r"\[[\s\S]*\]",tx_clean)
  if m:
   try:
    json_str = m.group()
    # 1. Quita comas huérfanas al final de listas o diccionarios
    json_str = re.sub(r',(\s*[\]}])', r'', json_str)
    # 2. Quita saltos de línea y tabulaciones raras
    json_str = json_str.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
    _nombres_bajos = [x.lower().replace("-", " ").replace("‑", " ").replace("—", " ") for x in nombres]
    
    data_parsed = []
    # Intento 1: Parseo nativo
    import json, ast
    try:
        data_parsed = json.loads(json_str)
    except Exception:
        # Intento 2: Reparación manual muy agresiva
        # Reemplazar valores falsamente booleanos
        json_str_py = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
        try:
            data_parsed = ast.literal_eval(json_str_py)
        except Exception:
            # Intento 3: Extracción regex de diccionarios (cuando hay texto pegado fuera o un error irrecuperable en un elemento)
            # Buscamos bloques que empiecen con {"nombre" y acaben con } 
            # Es un parche final, pero a veces salva la mitad de las herramientas.
            objetos = re.findall(r'\{[^{}]*"nombre"[^{}]*\}', json_str_py)
            if not objetos:
                raise Exception("El JSON estaba completamente roto y no tenía estructura.")
            for obj_str in objetos:
                try:
                    data_parsed.append(ast.literal_eval(obj_str))
                except:
                    pass
            if not data_parsed:
                raise Exception("No se pudo rescatar ningún objeto.")
                
    for h in data_parsed:
     nm_limpio = h.get("nombre","").lower().replace("-", " ").replace("‑", " ").replace("—", " ")
     
     # Check if a very similar name already exists (fuzzy matching)
     existe = False
     for existente in _nombres_bajos:
         if nm_limpio == existente or (len(nm_limpio) > 5 and (nm_limpio in existente or existente in nm_limpio)):
             existe = True
             break
     
     if not existe:
      c.append(h)
   except Exception as ex:
    warn(f"No se pudo parsear el JSON de IA: {ex}")
  print(f"OpenRouter: {len(c)} detectadas")

# ─────────────────────────────────────────────────────────────
# 3) Heurística (respaldo si OpenRouter no detectó nada)
# ─────────────────────────────────────────────────────────────
if not c:
 if G and not ia_ok:
  warn("IA OpenRouter no funcionó este ciclo; usando heurística de respaldo.")
 print("Heuristicas...")
 ps=[
  r'(?:launches?|launched|releases?|released|introduces?|unveils?)\s+(?:the\s+)?(?:new\s+)?(?:AI\s+)?(?:tool|platform|assistant|model|app)\s+(?:called|named)?\s+\u201c?([A-Z][A-Za-z0-9\s\-\.]{3,40})\u201d?',
  r'\u201c([A-Z][A-Za-z0-9\s\-\.]{3,40})\u201d\s*(?:,?\s*(?:a|the)\s+)?(?:new\s+)?(?:AI\s+)?(?:tool|platform)',
 ]
 for x in n:
  tx=x["ti"]+" "+x["re"]
  for p in ps:
   for m in re.findall(p,tx,re.IGNORECASE):
    nm=m.strip().strip('"').strip('\u201c').strip('\u201d')
    if 3<len(nm)<50 and nm.lower() not in ("the new","a new","this","that"):
     if nm.lower() not in [y.lower() for y in nombres]:
      c.append({"nombre":nm,"ti":x["ti"],"re":x["re"][:300],"li":x.get("li","")})
 print(f"Heuristicas: {len(c)} candidatos")

# ─────────────────────────────────────────────────────────────
# 2b) PRODUCT HUNT como fuente DIRECTA de lanzamientos.
#     Es un feed de productos nuevos por definición, así que cada entrada
#     es una herramienta candidata (no hay que "decidir si existe").
#     Limpiamos el nombre/descr y dejamos que el paso 4 + IA la enriquezcan.
# ─────────────────────────────────────────────────────────────
def _ph_candidatos(items, conocidas):
 out=[]
 conoc=set(x.lower() for x in conocidas)
 RUIDO=("access controls","mcp client","artifacts","research index","unreal engine")
 for x in items:
  if "producthunt" not in (x.get("fuente","") or ""): continue
  nm=(x.get("ti") or "").strip()
  desc=re.sub(r"\s+"," ",(x.get("re") or "")).replace("Discussion","").replace("Link","").strip(" |\n")
  if not nm or not (2<=len(nm)<=42): continue
  low=nm.lower()
  if low in conoc: continue
  # descartar entradas que son "features" de productos ya conocidos
  if any(r in low for r in RUIDO): continue
  if len(desc)<12: continue   # necesita una descripción mínima
  out.append({"nombre":nm,"descripcion":desc[:200],"li":x.get("li",""),
              "re":desc[:300],"ti":nm,"_ph":True})
 return out

ph=_ph_candidatos(n, nombres)
# Evitar duplicados con lo ya detectado por Gemini/heurística
_ya=set((x.get("nombre","") or "").lower().replace("-", " ").replace("‑", " ").replace("—", " ") for x in c)
_nombres_conocidos_bajos = [x.lower().replace("-", " ").replace("‑", " ").replace("—", " ") for x in nombres]

nuevas_ph = []
for x in ph:
    nm_ph = x["nombre"].lower().replace("-", " ").replace("‑", " ").replace("—", " ")
    
    # Skip if it's already in the AI candidate list 'c'
    existe_en_c = False
    for ya in _ya:
        if nm_ph == ya or (len(nm_ph) > 5 and (nm_ph in ya or ya in nm_ph)):
            existe_en_c = True
            break
            
    # Skip if it's already in the database
    existe_en_db = False
    if not existe_en_c:
        for existente in _nombres_conocidos_bajos:
            if nm_ph == existente or (len(nm_ph) > 5 and (nm_ph in existente or existente in nm_ph)):
                existe_en_db = True
                break
                
    if not existe_en_c and not existe_en_db:
        nuevas_ph.append(x)
# Control de crecimiento: no añadir nuevas si ya hay muchas pendientes sin cerrar.
# Así el catálogo no crece sin control y se da tiempo a completar/cerrar las previas.
_pend_actuales=sum(1 for h in t if h.get("pendiente_revision"))
CUPO_PENDIENTES=6        # tope de pendientes simultáneas (menos = se enriquecen mejor)
ALTAS_POR_CICLO=4        # máximo de altas nuevas por ejecución (deja cuota para enriquecer)
_hueco=max(0, CUPO_PENDIENTES-_pend_actuales)
_limite=min(ALTAS_POR_CICLO, _hueco)
if nuevas_ph and _limite>0:
 print(f"Product Hunt: {len(nuevas_ph)} candidatos; se añaden {min(len(nuevas_ph),_limite)} (pendientes actuales: {_pend_actuales})")
 c.extend(nuevas_ph[:_limite])
elif nuevas_ph:
 print(f"Product Hunt: {len(nuevas_ph)} candidatos, pero hay {_pend_actuales} pendientes (cupo {CUPO_PENDIENTES}). No se añaden nuevas este ciclo.")

# ─────────────────────────────────────────────────────────────
# 2c) ENRIQUECER con IA OpenRouter las fichas de los candidatos (tipo, funciones,
#     características, ética y precio). Si OpenRouter no está o falla, las fichas
#     quedan como "pendiente_revision" (paso 4) y se reintentan en el próximo ciclo.
# ─────────────────────────────────────────────────────────────
def enriquecer_con_ia(lista):
 """Rellena tipo/funciones/etica/etc. de cada dict de 'lista' usando Gemini.
 Devuelve cuántas fichas se enriquecieron. No rompe si IA falla."""
 if not G or not lista:return 0
 enr_total=0
 # Procesar en bloques de 10 para no saltarse ninguna
 for i in range(0, len(lista), 10):
  chunk = lista[i:i+10]
  try:
   lote=[{"nombre":x.get("nombre",""),"pista":(x.get("re") or x.get("descripcion") or "")[:160].replace("Nueva herramienta detectada automáticamente.", "").strip()} for x in chunk]
   pe=(
    "Eres un analista para un catálogo de herramientas de IA en español. "
    "Para cada herramienta de la lista, devuelve su ficha. Usa la pista como contexto; "
    "si no conoces algún dato, infiérelo de forma razonable. "
    "Devuelve SOLO un array JSON, un objeto por herramienta EN EL MISMO ORDEN, con campos: "
    "nombre (MANTÉN el nombre exacto que te doy), compania, tipo (p.ej. 'Generación de vídeo', 'Asistente de programación', "
    "'Chatbot / Asistente', 'Productividad', 'Agentes IA'...), "
    "precio (Gratuito|Freemium|Pago), descripcion (1-2 frases en español), "
    "funciones (array 3-5 en español), caracteristicas (array 3-5 en español), "
    "etica (1-2 frases en español sobre privacidad/sesgos/impacto), "
    "limite_gratis (1 frase en español: qué ofrece o qué limita el plan GRATUITO; "
    "si la herramienta es de pago sin plan gratis, pon 'Sin plan gratuito'). "
    "LISTA:\n"+json.dumps(lote,ensure_ascii=False)
   )
   tx2,ok2=llamar_ia(pe)
   if not tx2: continue
   m2=re.search(r"\[[\s\S]*\]",tx2)
   if not m2: continue
   fichas=json.loads(m2.group())
   # Búsqueda más flexible (contiene)
   for x in chunk:
    nombre_x = (x.get("nombre","") or "").strip().lower()
    f_encontrada = None
    for f in fichas:
     if not isinstance(f, dict): continue
     nombre_f = (f.get("nombre","") or "").strip().lower()
     # Permitir match si empieza igual o es muy parecido
     if nombre_x == nombre_f or (nombre_f and nombre_x.startswith(nombre_f)) or (nombre_x and nombre_f.startswith(nombre_x)):
      f_encontrada = f
      break
    
    if not f_encontrada: continue
    for campo in ("compania","tipo","precio","descripcion","funciones","caracteristicas","etica","limite_gratis"):
     if f_encontrada.get(campo): x[campo]=f_encontrada[campo]
    enr_total+=1
  except Exception as ex:
   warn(f"Fallo enriqueciendo con IA OpenRouter: {ex}")
 return enr_total

def buscar_en_internet(query):
 try:
  from ddgs import DDGS
  resultados = DDGS().text(query, max_results=3)
  return "\n".join([f"[{r.get('href')}] {r.get('body')}" for r in resultados])
 except Exception:
  return ""

def completar_webs_con_ia(lista):
 """Pide a IA la URL OFICIAL de cada herramienta buscando en Internet de verdad (vía DuckDuckGo)."""
 if not G or not lista:return 0
 try:
  lote=[]
  print(f"  Buscando en internet {len(lista)} herramientas...")
  for x in lista:
   import time
   time.sleep(1) # Pequeña pausa para no saturar DuckDuckGo
   contexto_web = buscar_en_internet(x.get("nombre","") + " AI tool official website")
   lote.append({
       "nombre": x.get("nombre",""),
       "resultados_de_google": contexto_web,
       "web_provisional": x.get("web","")
   })
   
  pw=(
   "Eres un investigador web. Te doy una lista de herramientas de IA junto con los primeros resultados de búsqueda de Google (DuckDuckGo) para cada una. "
   "Tu tarea es leer esos resultados reales de internet y extraer la URL OFICIAL de la herramienta. "
   "Devuelve SOLO un array JSON, un objeto por elemento EN EL MISMO ORDEN, con los campos: nombre, web. "
   "REGLAS CRÍTICAS: "
   "1. Usa SÓLO las URLs que veas en los 'resultados_de_google'. No inventes dominios. "
   "2. Descarta agregadores como producthunt.com, saashub.com, linkedin.com o noticias. Queremos la web de la startup o su GitHub. "
   "3. Si los resultados de Google no muestran la web oficial clara, devuelve la 'web_provisional' que te doy o déjalo vacío \"\".\n"
   "LISTA:\n"+json.dumps(lote,ensure_ascii=False)
  )
  txw,okw=llamar_ia(pw)
  if not txw:return 0
  mw=re.search(r"\[[\s\S]*\]",txw)
  if not mw:return 0
  fichas=json.loads(mw.group())
  porn={(f.get("nombre","") or "").strip().lower():f for f in fichas if isinstance(f,dict)}
  hechas=0
  for x in lista:
   f=porn.get((x.get("nombre","") or "").strip().lower())
   if not f:continue
   w=(f.get("web","") or "").strip()
   # Solo sustituir si Gemini da una web OFICIAL (no otro agregador) y distinta.
   if es_web_oficial(w) and w!=x.get("web",""):
    x["web"]=w
    hechas+=1
  return hechas
 except Exception as ex:
  warn(f"Fallo completando webs con IA OpenRouter: {ex}")
  return 0

if G and c:
 n_enr=enriquecer_con_ia(c)
 if n_enr:print(f"IA OpenRouter enriqueció {n_enr} fichas nuevas")

# ─────────────────────────────────────────────────────────────
# 4) Normalizar candidatos. Lo que llegue incompleto se marca
#    como pendiente_revision para NO ensuciar la sección ética.
# ─────────────────────────────────────────────────────────────
def deducir_tipo(texto):
 """Deduce una categoría razonable a partir de palabras clave de la descripción."""
 t=(texto or "").lower()
 reglas=[
  ("Generación de vídeo",["video","vídeo","film","movie"]),
  ("Generación de imágenes",["image","imagen","photo","foto","picture","art ","diffusion"]),
  ("Generación de audio/voz",["voice","voz","audio","speech","music","música","sound","podcast"]),
  ("Asistente de programación",["code","código","coding","developer","program","ide","debug","terminal","devtool"]),
  ("Agentes IA",["agent","agente","autonomous","autónomo","workflow"]),
  ("Productividad",["note","nota","meeting","reunión","document","slide","presentation","email","calendar","task","writing","escribir","resume"]),
  ("Búsqueda / Investigación",["search","búsqueda","research","investigación","scrape","index"]),
  ("Chatbot / Asistente",["chat","assistant","asistente","conversational","companion"]),
  ("Seguridad",["security","seguridad","vulnerab","pentest","threat","defense"]),
  ("Datos / Análisis",["data","datos","analytics","análisis","database","sql","memory"]),
 ]
 for tipo,kws in reglas:
  if any(k in t for k in kws):return tipo
 return "Herramienta de IA"
def ok_lista(v):
 return isinstance(v,list) and len(v)>0 and not (len(v)==1 and str(v[0]).strip().lower() in ("pendiente","automatico","automático",""))
def ok_txt(v):
 return isinstance(v,str) and len(v.strip())>15 and "pendiente" not in v.lower()
# Dominios de agregadores/noticias: NO son la web oficial de la herramienta.
_DOMINIOS_AGREGADORES=("producthunt.com","news.ycombinator.com","ycombinator.com",
 "techcrunch.com","theverge.com","venturebeat.com","arstechnica.com","wired.com",
 "zdnet.com","technologyreview.com","reddit.com","huggingface.co/papers",
 "marktechpost.com","the-decoder.com","dailyai.com","syncedreview.com")
def es_web_oficial(v):
 """URL válida que además NO sea de un agregador/medio de noticias."""
 if not url_valida(v):return False
 low=v.lower()
 return not any(dom in low for dom in _DOMINIOS_AGREGADORES)
def limpiar_web(x):
 """Devuelve la web oficial si la hay. Si solo hay enlace a agregador (ej. ProductHunt),
 DEVUELVE ESE ENLACE provisionalmente para que la web no se quede en blanco desde el día 1.
 La función de Backfill intentará sustituirlo por el oficial en el futuro."""
 for cand in (x.get("web"),x.get("li"),x.get("enlace")):
  if es_web_oficial(cand): return cand.strip()
 # Si no hay oficial, devolvemos el provisional (ProductHunt) en vez de vacío
 for cand in (x.get("web"),x.get("li"),x.get("enlace")):
  if url_valida(cand): return cand.strip()
 return ""

new=[]
for x in c:
 nm=x.get("nombre","")
 if not nm:continue
 ctx=(x.get("ti","")+" "+x.get("re","")+" "+x.get("descripcion","")).lower()
 gr=any(w in ctx for w in ["free","gratis","gratuito","open source"])
 pa=any(w in ctx for w in ["paid","pago","subscription","premium","plan","$"])
 pr=x.get("precio","Freemium")
 if pr not in ("Gratuito","Freemium","Pago"):
  pr="Gratuito" if (gr and not pa) else ("Pago" if (pa and not gr) else "Freemium")
 x["precio"]=pr

 # Detectar si la ficha está completa o necesita revisión humana
 incompleta=not(ok_txt(x.get("descripcion","")) and ok_lista(x.get("funciones")) and ok_lista(x.get("caracteristicas")) and ok_txt(x.get("etica","")))

 x.setdefault("descripcion","Nueva herramienta detectada automáticamente. "+x.get("re","")[:180])
 if not ok_lista(x.get("funciones")):x["funciones"]=["Pendiente de revisión"]
 if not ok_lista(x.get("caracteristicas")):x["caracteristicas"]=["Detectada automáticamente"]
 if not ok_txt(x.get("etica","")):x["etica"]="Ficha pendiente de revisión ética. Aún no verificada."
 x["web"]=limpiar_web(x)
 x.setdefault("tipo","Otros")
 x.setdefault("compania","Desconocida")
 x["id"]=re.sub(r"[^a-z0-9]","-",nm.lower().strip())+"-"+hashlib.md5(nm.encode()).hexdigest()[:6]
 x["gratis"]=gr or pr in ("Freemium","Gratuito")
 x["pago"]=pa or pr in ("Freemium","Pago")
 x["fecha_agregado"]=datetime.now(timezone.utc).strftime("%Y-%m-%d")
 x["auto_detectado"]=True
 x["pendiente_revision"]=incompleta
 # limpiar campos temporales del feed
 for k in ("ti","re","li","_ph","enlace","medio","fuente"):x.pop(k,None)
 if x["id"] not in ids:new.append(x);ids.add(x["id"])

print(f"Nuevas: {len(new)}")
for h in new:
 flag=" ⚠️PENDIENTE" if h.get("pendiente_revision") else ""
 print("  + "+h["nombre"]+" ["+h.get("tipo","?")+"] ["+h.get("precio","?")+"]"+flag)
if new:
 t.extend(new)

# ─────────────────────────────────────────────────────────────
# 5) AUTONOMÍA TOTAL: reprocesar las herramientas que sigan "pendiente_revision"
#    de ciclos anteriores. Sin intervención humana:
#      a) Se reintenta completarlas con IA OpenRouter (si hay clave/cuota).
#      b) Si una ficha lleva demasiados ciclos pendiente y IA nunca pudo,
#         se completa con un texto autonomo derivado de su descripcion y se
#         marca como verificada igualmente (nada se queda "sin verificar" para
#         siempre). Así la etiqueta 🆕 desaparece sola.
# ─────────────────────────────────────────────────────────────
MAX_CICLOS_PENDIENTE=3   # tras 3 intentos, se cierra la ficha automáticamente

def ficha_completa(x):
 return (ok_txt(x.get("descripcion","")) and ok_lista(x.get("funciones"))
         and ok_lista(x.get("caracteristicas")) and ok_txt(x.get("etica","")))

pend=[h for h in t if h.get("pendiente_revision")]
if pend:
 print(f"Pendientes de ciclos anteriores: {len(pend)}")
 # a) reintento con IA OpenRouter
 n_re=enriquecer_con_ia(pend)
 if n_re:print(f"  IA OpenRouter completó {n_re} pendientes")
 # b) cierre automático: completar lo que falte y quitar la etiqueta
 cerradas=0
 for h in pend:
  h["intentos_auto"]=int(h.get("intentos_auto",0))+1
  # Normalizar precio si hiciera falta
  if h.get("precio") not in ("Gratuito","Freemium","Pago"):h["precio"]="Freemium"
  if ficha_completa(h):
   h["pendiente_revision"]=False
   h.pop("intentos_auto",None)
   cerradas+=1
  elif h["intentos_auto"]>=MAX_CICLOS_PENDIENTE:
   # Red de seguridad: rellenar lo que falte de forma autónoma y cerrar.
   base=re.sub(r"\s+"," ",(h.get("descripcion") or h.get("nombre",""))).strip()
   if not ok_txt(h.get("descripcion","")):
    h["descripcion"]=(base or h.get("nombre","Herramienta de IA"))[:200]
   if not ok_lista(h.get("funciones")):
    h["funciones"]=["Herramienta de IA","Ver sitio oficial para más detalles"]
   if not ok_lista(h.get("caracteristicas")):
    h["caracteristicas"]=["Detectada automáticamente desde fuentes de IA","Información basada en su lanzamiento"]
   if not ok_txt(h.get("etica","")):
    h["etica"]=("Ficha generada automáticamente; conviene contrastar su política "
                "de privacidad y uso de datos en el sitio oficial antes de usarla.")
   # Deducir un tipo razonable de la descripción (mejor que "Otros").
   if h.get("tipo") in (None,"","Otros"):h["tipo"]=deducir_tipo(base)
   h["pendiente_revision"]=False
   h.pop("intentos_auto",None)
   cerradas+=1
 if cerradas:print(f"  Cerradas automáticamente (etiqueta 🆕 retirada): {cerradas}")

# ─────────────────────────────────────────────────────────────
# 5b) SANEADO de webs inválidas. Convierte valores como "No especificado"
#     en cadena vacía para que la web no muestre enlaces rotos.
# ─────────────────────────────────────────────────────────────
webs_limpiadas=0
for h in t:
 w=h.get("web","")
 # Solo vaciar webs realmente INVÁLIDAS. Las de agregadores (producthunt) se vacían SOLO cuando entran 
 # en la función de backfill, para no dejarlas en blanco hasta que la IA encuentre su reemplazo.
 if w and not url_valida(w):
  h["web"]=""
  webs_limpiadas+=1
if webs_limpiadas:print(f"Webs inválidas saneadas: {webs_limpiadas}")

# ─────────────────────────────────────────────────────────────
# 5b-bis) VERIFICADOR de enlaces vivos. Cada ciclo comprueba unas pocas webs
#     (rotando para cubrir todo el catálogo poco a poco). Si una está CAÍDA
#     (dominio inexistente o 404/410), vacía su web para que el backfill (5c)
#     le busque una URL nueva con IA OpenRouter. Conservador: no borra por timeouts.
# ─────────────────────────────────────────────────────────────
COMPROBAR_POR_CICLO=12
con_web=[h for h in t if url_valida(h.get("web",""))]
caidas=0
if con_web:
 # Punto de inicio rotatorio derivado del día del año: cada ejecución empieza
 # en un tramo distinto, así con los ciclos se cubre todo el catálogo sin
 # necesidad de guardar estado entre ejecuciones (el runner es efímero).
 dia=int(datetime.now(timezone.utc).strftime("%j"))   # 1..366
 pos=(dia*COMPROBAR_POR_CICLO)%len(con_web)
 lote=[con_web[(pos+i)%len(con_web)] for i in range(min(COMPROBAR_POR_CICLO,len(con_web)))]
 for h in lote:
  if not enlace_vivo(h.get("web","")):
   print(f"  Enlace caído: {h.get('nombre','')} -> {h.get('web','')}")
   h["web"]=""          # se vaciará y el backfill 5c buscará una nueva
   caidas+=1
 print(f"Verificador de enlaces: {len(lote)} comprobados, {caidas} caídos.")

# ─────────────────────────────────────────────────────────────
# 5c) BACKFILL de webs faltantes. Cada ciclo, IA intenta encontrar la URL
#     oficial de unas pocas herramientas sin web válida. Si no la sabe con
#     seguridad, la deja vacía (la web mostrará "no disponible"). Sin clave, nada.
# ─────────────────────────────────────────────────────────────
# Incluye las que no tienen web Y las que apuntan a un agregador (Product Hunt, etc.)
# Intentar mejorar las que no tienen web o usan un agregador
sin_web=[h for h in t if not es_web_oficial(h.get("web",""))]
# Ordenar por intentos_web para no quedarnos atascados en las que Gemini no sabe
sin_web.sort(key=lambda h: h.get("intentos_web", 0))

webs_rellenadas=0
if G and sin_web:
 batch_web = sin_web[:20]
 print(f"Backfill 'web': {len(sin_web)} sin web oficial; intentando {len(batch_web)} este ciclo...")
 for h in batch_web:
  h["intentos_web"] = h.get("intentos_web", 0) + 1
 webs_rellenadas=completar_webs_con_ia(batch_web)
 print(f"  Webs encontradas automáticamente: {webs_rellenadas}")
elif sin_web:
 print(f"Backfill 'web' pendiente ({len(sin_web)} sin URL), pero no hay clave OpenRouter.")

# ─────────────────────────────────────────────────────────────
# 6) BACKFILL del límite del plan gratuito (limite_gratis).
#    Rellena cada ciclo, poco a poco, las herramientas que aún no lo tengan,
#    priorizando las Freemium. Con IA; sin él, no hace nada (no rompe).
#    Lote pequeño para no agotar la cuota: el catálogo se completa en varios ciclos.
# ─────────────────────────────────────────────────────────────
def _falta_lg(h):
 v=h.get("limite_gratis","")
 return not (isinstance(v,str) and len(v.strip())>3)

sin_lg=[h for h in t if _falta_lg(h)]
# Las Freemium/Gratuito primero (son las que más interesan a los usuarios)
sin_lg.sort(key=lambda h: 0 if str(h.get("precio","")).lower().startswith(("freemium","gratuito")) else 1)
backfill=sin_lg[:20]
backfill_cambios=0
if G and backfill:
 print(f"Backfill 'plan gratuito': {len(sin_lg)} sin dato; procesando {len(backfill)} este ciclo...")
 antes={id(h):h.get("limite_gratis","") for h in backfill}
 enriquecer_con_ia(backfill)   # rellena limite_gratis (y completa huecos)
 for h in backfill:
  v=h.get("limite_gratis","")
  if isinstance(v,str) and len(v.strip())>3 and v!=antes[id(h)]:
   backfill_cambios+=1
 print(f"  Completadas con límite gratis: {backfill_cambios}")
elif backfill:
 print(f"Backfill 'plan gratuito' pendiente ({len(sin_lg)} sin dato), pero no hay clave OpenRouter.")

# Guardar si hubo altas nuevas, cambios en pendientes o backfill
if new or pend or backfill_cambios or webs_limpiadas or webs_rellenadas or caidas:
 with open(J,"w",encoding="utf-8") as f:json.dump(t,f,ensure_ascii=False,indent=2)
 print(f"JSON: {len(t)} herramientas")
else:
 print("Sin novedades")
print(f"Total: {len(t)}")
