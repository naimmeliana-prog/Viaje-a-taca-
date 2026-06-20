import json,re,sys,hashlib,os
from datetime import datetime,timezone
from pathlib import Path

J=Path(__file__).parent/"herramientas.json"
G=os.environ.get("GEMINI_API_KEY","")
MODO_PRUEBA=os.environ.get("MODO_PRUEBA","")=="1"

# Modelos a probar en orden. Se puede forzar uno con la variable GEMINI_MODEL.
# Los *-lite suelen tener cuota gratuita más generosa (menos errores 429).
_modelo_env=os.environ.get("GEMINI_MODEL","").strip()
MODELOS=[_modelo_env] if _modelo_env else [
 "gemini-2.0-flash-lite",
 "gemini-2.5-flash",
 "gemini-2.0-flash",
]
REINTENTOS=3          # intentos por modelo ante un 429
ESPERA_BASE=20        # segundos; se multiplica en cada reintento (20, 40, 60)

# Anotaciones visibles en GitHub Actions (salen resaltadas en rojo/amarillo)
def err(m):print("::error::"+m)
def warn(m):print("::warning::"+m)

if not J.exists():err("no existe herramientas.json");sys.exit(1)
with open(J) as f:t=json.load(f)
t=[h for h in t if not h.get("es_prueba")]
print(f"Actuales: {len(t)}")
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
  ("https://wwwhatsnew.com/tag/inteligencia-artificial/feed/","WWWhat's new"),
  ("https://planetachatbot.com/feed/","Planeta Chatbot"),
  ("https://blogthinkbig.com/feed","Think Big"),
 ]
 # Feeds en español dedicados a ÉTICA / regulación / privacidad (verificados).
 FEEDS_ETI=[
  ("https://www.xataka.com/tag/etica/rss2.xml","Xataka"),
  ("https://www.xataka.com/tag/regulacion/rss2.xml","Xataka"),
  ("https://wwwhatsnew.com/tag/etica/feed/","WWWhat's new"),
  ("https://blogthinkbig.com/tag/etica/feed","Think Big"),
  ("https://www.genbeta.com/tag/privacidad/rss2.xml","Genbeta"),
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
gemini_ok=False

# ─────────────────────────────────────────────────────────────
# 2) Análisis con Gemini (fuente principal de detección)
# ─────────────────────────────────────────────────────────────
def llamar_gemini(prompt):
 """Devuelve (texto, True) si responde 200. Recorre MODELOS y reintenta
 ante un 429 (cuota) con espera creciente. Si todos fallan, (None, False)."""
 import time
 import requests as rq
 cuota=False
 for modelo in MODELOS:
  url="https://generativelanguage.googleapis.com/v1beta/models/"+modelo+":generateContent?key="+G
  for intento in range(1,REINTENTOS+1):
   try:
    rp=rq.post(url,
     json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1}},
     timeout=40)
   except Exception as ex:
    warn(f"[{modelo}] error de red (intento {intento}): {ex}")
    time.sleep(ESPERA_BASE)
    continue
   if rp.status_code==200:
    print(f"✓ Gemini OK con modelo {modelo}")
    try:
     return rp.json()["candidates"][0]["content"]["parts"][0]["text"],True
    except Exception as ex:
     warn(f"[{modelo}] respuesta 200 pero ilegible: {ex}")
     return None,True
   if rp.status_code==429:
    cuota=True
    if intento<REINTENTOS:
     espera=ESPERA_BASE*intento
     warn(f"[{modelo}] cuota agotada (429). Reintento {intento}/{REINTENTOS-1} en {espera}s...")
     time.sleep(espera)
     continue
    else:
     warn(f"[{modelo}] 429 tras {REINTENTOS} intentos. Probando siguiente modelo...")
     break
   if rp.status_code in (400,403,404):
    warn(f"[{modelo}] HTTP {rp.status_code} ({rp.text[:120]}). Probando siguiente modelo...")
    break
   warn(f"[{modelo}] HTTP {rp.status_code}: {rp.text[:120]}")
   break
 if cuota:
  err("Todos los modelos de Gemini devolvieron 429 (cuota agotada). "
      "Espera al reinicio diario del cupo o revisa tu plan: https://ai.google.dev/gemini-api/docs/rate-limits")
 else:
  err("No se pudo obtener respuesta de Gemini con ningún modelo. Se usará la heurística.")
 return None,False

if not G:
 warn("Falta el secret GEMINI_API_KEY (ITACA). Se usará solo la heurística, mucho menos fiable.")
elif n:
 print("🤖 Gemini analizando (modelos: "+", ".join(MODELOS)+")...")
 # Muestra repartida entre fuentes (round-robin) para que Gemini no vea
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
 tx,gemini_ok=llamar_gemini(p)
 if tx:
  m=re.search(r"\[[\s\S]*\]",tx)
  if m:
   try:
    for h in json.loads(m.group()):
     if h.get("nombre","").lower() not in [x.lower() for x in nombres]:
      c.append(h)
   except Exception as ex:
    warn(f"No se pudo parsear el JSON de Gemini: {ex}")
  print(f"Gemini: {len(c)} detectadas")

# ─────────────────────────────────────────────────────────────
# 3) Heurística (respaldo si Gemini no detectó nada)
# ─────────────────────────────────────────────────────────────
if not c:
 if G and not gemini_ok:
  warn("Gemini no funcionó este ciclo; usando heurística de respaldo.")
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
# 4) Normalizar candidatos. Lo que llegue incompleto se marca
#    como pendiente_revision para NO ensuciar la sección ética.
# ─────────────────────────────────────────────────────────────
def ok_lista(v):
 return isinstance(v,list) and len(v)>0 and not (len(v)==1 and str(v[0]).strip().lower() in ("pendiente","automatico","automático",""))
def ok_txt(v):
 return isinstance(v,str) and len(v.strip())>15 and "pendiente" not in v.lower()

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
 x.setdefault("web",x.get("li",""))
 x.setdefault("tipo","Otros")
 x.setdefault("compania","Desconocida")
 x["id"]=re.sub(r"[^a-z0-9]","-",nm.lower().strip())+"-"+hashlib.md5(nm.encode()).hexdigest()[:6]
 x["gratis"]=gr or pr in ("Freemium","Gratuito")
 x["pago"]=pa or pr in ("Freemium","Pago")
 x["fecha_agregado"]=datetime.now(timezone.utc).strftime("%Y-%m-%d")
 x["auto_detectado"]=True
 x["pendiente_revision"]=incompleta
 # limpiar campos temporales del feed
 for k in ("ti","re","li"):x.pop(k,None)
 if x["id"] not in ids:new.append(x);ids.add(x["id"])

print(f"Nuevas: {len(new)}")
if new:
 for h in new:
  flag=" ⚠️PENDIENTE" if h.get("pendiente_revision") else ""
  print("  + "+h["nombre"]+" ["+h.get("tipo","?")+"] ["+h.get("precio","?")+"]"+flag)
 t.extend(new)
 with open(J,"w",encoding="utf-8") as f:json.dump(t,f,ensure_ascii=False,indent=2)
 print(f"JSON: {len(t)} herramientas")
else:
 print("Sin novedades")
print(f"Total: {len(t)}")
