import json,re,sys,hashlib,os
from datetime import datetime,timezone
from pathlib import Path

J=Path(__file__).parent/"herramientas.json"
G=os.environ.get("GEMINI_API_KEY","")
MODO_PRUEBA=os.environ.get("MODO_PRUEBA","")=="1"

if not J.exists():print("ERROR: no json");sys.exit(1)
with open(J) as f:t=json.load(f)
t=[h for h in t if not h.get("es_prueba")]
print(f"Actuales: {len(t)}")
ids={h["id"] for h in t}
nombres=[h["nombre"] for h in t]

# MODO PRUEBA
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

try:
 import feedparser
 n=[]
 for u in [
  "https://techcrunch.com/category/artificial-intelligence/feed/",
  "https://venturebeat.com/category/ai/feed/",
  "https://www.artificialintelligence-news.com/feed/",
  "https://www.theregister.com/software/ai_ml/headlines.atom"
 ]:
  try:
   f=feedparser.parse(u)
   for e in f.entries[:20]:
    n.append({"ti":e.get("title",""),"re":re.sub(r"<[^>]+>","",e.get("summary",e.get("description",""))),"li":e.get("link","")})
  except:pass
 print(f"Noticias: {len(n)}")
except:
 n=[];print("Sin RSS")

c=[]

if G and n:
 print("🤖 Gemini analizando...")
 try:
  import requests as rq
  hdr="\n".join([x["ti"] for x in n[:30]])
  known=", ".join(nombres[:40])
  p="Find NEW AI tools launched from these headlines. KNOWN: "+known+"\n\nHEADLINES:\n"+hdr+"\n\nReturn ONLY JSON array. Each: nombre, compania, tipo, precio, descripcion, web. If none, []."
  rp=rq.post(
   "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="+G,
   json={"contents":[{"parts":[{"text":p}]}],"generationConfig":{"temperature":0.1}},
   timeout=30
  )
  if rp.status_code==200:
   tx=rp.json()["candidates"][0]["content"]["parts"][0]["text"]
   m=re.search(r"\[[\s\S]*\]",tx)
   if m:
    for h in json.loads(m.group()):
     if h.get("nombre","").lower() not in [x.lower() for x in nombres]:
      c.append(h)
  print(f"Gemini: {len(c)} detectadas")
 except Exception as ex:
  print(f"Error Gemini: {ex}")

if not c:
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
 x.setdefault("descripcion","Nueva herramienta. "+x.get("re","")[:180])
 x.setdefault("funciones",["Pendiente"])
 x.setdefault("caracteristicas",["Automatico"])
 x.setdefault("etica","Info pendiente.")
 x.setdefault("web",x.get("li",""))
 x.setdefault("tipo","Otros")
 x.setdefault("compania","Desconocida")
 x["id"]=re.sub(r"[^a-z0-9]","-",nm.lower().strip())+"-"+hashlib.md5(nm.encode()).hexdigest()[:6]
 x["gratis"]=gr or pr=="Freemium"
 x["pago"]=pa or pr=="Freemium"
 x["fecha_agregado"]=datetime.now(timezone.utc).strftime("%Y-%m-%d")
 x["auto_detectado"]=True
 if x["id"] not in ids:new.append(x);ids.add(x["id"])

print(f"Nuevas: {len(new)}")
if new:
 for h in new:
  print("  + "+h["nombre"]+" ["+h.get("tipo","?")+"] ["+h.get("precio","?")+"]")
 t.extend(new)
 with open(J,"w",encoding="utf-8") as f:json.dump(t,f,ensure_ascii=False,indent=2)
 print(f"JSON: {len(t)} herramientas")
else:
 print("Sin novedades")
print(f"Total: {len(t)}")
