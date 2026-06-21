# 🧭 Viaje a Ítaca — Guía ética de herramientas de IA

> «Cuando emprendas tu viaje a Ítaca, pide que el camino sea largo,
> lleno de aventuras, lleno de experiencias.» — Konstantino Kavafis

**Viaje a Ítaca** es una guía práctica y ética sobre herramientas de
inteligencia artificial. Un catálogo navegable, un comparador, reflexión
ética y recursos para aprender — pensado para usar la IA con conciencia,
propósito y humanidad.

🌐 **Web:** https://viajeaitaca.great-site.net

---

## ✨ Lo que hace especial a este proyecto

Es un sitio **que se mantiene y se actualiza solo**, sin intervención humana.
Cada dos días:

1. Busca herramientas de IA **nuevas** en fuentes de lanzamientos (Product Hunt
   y medios de IA) y las **añade al catálogo automáticamente**.
2. **Completa la ficha** de cada herramienta nueva (descripción, tipo, funciones,
   características y nota ética) usando IA (Google Gemini).
3. Refresca una **barra lateral de noticias** de IA en español (novedades y ética).
4. Publica todo en la web automáticamente.

No hay que aprobar, revisar ni tocar nada. El proyecto sigue su rumbo solo. 🌅

---

## 🗺️ Cómo está montado

```
                 ┌──────────────────────────┐
   Cada 2 días → │  GitHub Actions (cron)   │
                 │  .github/workflows/      │
                 │     update-tools.yml     │
                 └────────────┬─────────────┘
                              │ ejecuta
                              ▼
                 ┌──────────────────────────┐
                 │     update_tools.py      │  ← el cerebro
                 │  · lee feeds RSS         │
                 │  · detecta herramientas  │
                 │  · enriquece con Gemini  │
                 │  · genera noticias.json  │
                 └────────────┬─────────────┘
                              │ escribe
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
      herramientas.json   noticias.json   (build_js.py)
              │               │                │
              └───────┬───────┴────────────────┘
                      │ commit + push (GitHub)
                      │ subida por FTP (InfinityFree)
                      ▼
        ┌──────────────────────────────────────┐
        │   Web en InfinityFree (htdocs/)       │
        │   · data/herramientas.js  (catálogo)  │
        │   · data/noticias.json    (barra)     │
        │   · barra-noticias.js     (widget)    │
        │   · *.html                (páginas)   │
        └──────────────────────────────────────┘
```

---

## 📁 Archivos del repositorio

| Archivo | Qué es |
|---|---|
| `update_tools.py` | **El cerebro.** Detecta herramientas, las enriquece con Gemini, genera las noticias y mantiene el catálogo. |
| `build_js.py` | Regenera `data/herramientas.js` a partir de `herramientas.json` (lo que consume la web). |
| `test_gemini.py` | Diagnóstico de la clave Gemini sin gastar cuota. |
| `herramientas.json` | El catálogo (fuente de datos principal). |
| `noticias.json` | Titulares de IA en español para la barra lateral. |
| `data/herramientas.js` | Catálogo embebido + cargador que lee el JSON en vivo. |
| `barra-noticias.js` | Widget de la barra lateral de noticias. |
| `*.html` | Las páginas del sitio (index, herramientas, comparador, etica, aprender). |
| `.github/workflows/update-tools.yml` | Automatización principal (cron cada 2 días). |
| `.github/workflows/test-gemini.yml` | Workflow manual para comprobar la clave Gemini. |
| `INSTRUCCIONES.md` | Guía detallada de despliegue y mantenimiento. |

---

## ⚙️ Cómo funciona la autoactualización (en detalle)

### 1. Detección de herramientas nuevas
- Lee ~19 feeds RSS de IA. **Product Hunt** es la fuente principal de
  lanzamientos: cada entrada es un producto nuevo por definición.
- Da de alta hasta **8 herramientas nuevas por ciclo**.
- Las herramientas ya conocidas (por `id`) nunca se duplican.

### 2. Fichas que se completan solas
- Las recién añadidas se marcan `"pendiente_revision": true` y aparecen en la web
  con la etiqueta **"🆕 reciente"**.
- Cada ciclo, **Gemini completa** las fichas pendientes (tipo, funciones, ética…).
  Cuando una ficha queda completa, la etiqueta **desaparece automáticamente**.
- **Garantía de cierre:** si Gemini no pudiera, tras **3 ciclos** la ficha se cierra
  igualmente con un texto autónomo. Nada se queda "reciente" para siempre.
- **Autorregulación:** si hay **12 pendientes** sin cerrar, no se añaden nuevas
  hasta resolverlas (el catálogo no crece sin control).

### 3. Robustez ante errores
- Si Gemini devuelve **error 429** (cuota), reintenta 3 veces con espera creciente
  y prueba varios modelos (`gemini-2.0-flash-lite` → `gemini-2.5-flash` →
  `gemini-2.0-flash`).
- Si todo falla, el sistema **no se rompe**: las fichas quedan pendientes y se
  reintentan en el siguiente ciclo.
- Los problemas se muestran como avisos visibles (⚠️/🔴) en el log de Actions.

### 4. Barra de noticias
- `noticias.json` se genera desde feeds **en español** (Xataka, Genbeta, WWWhat's
  new, Planeta Chatbot, Think Big…), con una pestaña de **Novedades** y otra de
  **Ética** (regulación, privacidad, sesgos…).
- La barra (`barra-noticias.js`) está en las páginas **Inicio** y **Ética**.

---

## 🔧 Configuración (una sola vez)

### Secrets en GitHub (`Settings → Secrets and variables → Actions`)
| Secret | Para qué | ¿Obligatorio? |
|---|---|---|
| `ITACA` | Clave de la API de Google Gemini (completa las fichas). | Recomendado |
| `FTP_HOST`, `FTP_USER`, `FTP_PASS` | Subir los datos a InfinityFree por FTP. | Opcional |

### Variable opcional
| Variable | Para qué |
|---|---|
| `GEMINI_MODEL` | Forzar un modelo concreto de Gemini. Si se deja vacío, se prueban varios en orden. |

> El sitio está alojado en **InfinityFree**. El workflow sube `herramientas.json`,
> `data/herramientas.js` y `noticias.json` a `htdocs/data/` por FTP.

---

## 🛠️ Mantenimiento

**Lo normal es no tener que hacer nada.** El sistema es autónomo. Aun así:

- **Lanzar una actualización manual:** Actions → *Actualizar herramientas IA* →
  *Run workflow*.
- **Probar la clave Gemini:** Actions → *Probar clave Gemini (ITACA)* →
  *Run workflow*.
- **Editar/borrar una herramienta a mano:** edita o elimina su bloque en
  `herramientas.json`.
- **Comprobar que la clave funciona en local:**
  ```bash
  GEMINI_API_KEY="tu_clave" python3 test_gemini.py
  ```

Para los detalles de despliegue paso a paso, ver **`INSTRUCCIONES.md`**.

---

## 🌿 Filosofía

La inteligencia artificial no es un fin; es un **medio**. Bien usada, amplifica lo
mejor de nosotros: la creatividad, la curiosidad, la capacidad de aprender y de
cuidar. Este proyecto quiere ayudar a navegarla con criterio y con alma.

El viaje, no el destino. 🧭

---

*Proyecto personal · Dominio público · Comparte, adapta, mejora.*
