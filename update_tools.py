import json,re,sys,hashlib,os
from datetime import datetime,timezone
from pathlib import Path

J=Path(__file__).parent/"herramientas.json"
G=os.environ.get("GEMINI_API_KEY","")
MODO_PRUEBA=os.environ.get("MODO_PRUEBA","")=="1"

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
 ]:
  try:
   f=feedparser.parse(u)
   for e in f.entries[:20]:
    n.append({"ti":e.get("title",""),"re":re.sub(r"<[^>]+>","",e.get("summary",e.get("description",""))),"li":e.get("link","")})
  except:pass
 print(f"Noticias: {len(n)}")
except:
 n=[];warn("feedparser no disponible: sin RSS")

if not n:
 warn("0 noticias recogidas de los feeds RSS (¿feeds caídos o red bloqueada?)")

c=[]
gemini_ok=False

# ─────────────────────────────────────────────────────────────
# 2) Análisis con Gemini (fuente principal de detección)
# ─────────────────────────────────────────────────────────────
if not G:
 warn("Falta el secret GEMINI_API_KEY (ITACA). Se usará solo la heurística, mucho menos fiable.")
elif n:
 print("🤖 Gemini analizando...")
 try:
  import requests as rq
  hdr="\n".join([x["ti"]+" — "+x["re"][:160] for x in n[:30]])
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
  rp=rq.post(
   "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="+G,
   json={"contents":[{"parts":[{"text":p}]}],"generationConfig":{"temperature":0.1}},
   timeout=40
  )
  if rp.status_code==200:
   gemini_ok=True
   tx=rp.json()["candidates"][0]["content"]["parts"][0]["text"]
   m=re.search(r"\[[\s\S]*\]",tx)
   if m:
    for h in json.loads(m.group()):
     if h.get("nombre","").lower() not in [x.lower() for x in nombres]:
      c.append(h)
   print(f"Gemini: {len(c)} detectadas")
  else:
   err(f"Gemini respondió HTTP {rp.status_code}: {rp.text[:200]}")
 except Exception as ex:
  err(f"Fallo llamando a Gemini: {ex}")

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
