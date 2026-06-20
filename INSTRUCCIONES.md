# 🧭 Viaje a Ítaca — Arreglo de la autoactualización

Estos archivos corrigen los 5 problemas detectados en la autoactualización.

## Qué se ha cambiado y por qué

| Archivo | Cambio |
|---|---|
| `data/herramientas.js` | El cargador ahora detecta cambios **por contenido (firma/hash)**, no solo "más herramientas". Lee primero el JSON local (`data/herramientas.json`, sin CORS) y usa GitHub como respaldo. Siempre re-renderiza al detectar novedades. |
| `update_tools.py` | Avisa de forma **visible** (`::error::`/`::warning::`) si falla la clave de Gemini o los feeds. Pide a Gemini fichas completas (con ética). Lo que entre incompleto se marca `pendiente_revision` y no contamina la sección ética. |
| `build_js.py` | **NUEVO.** Regenera `data/herramientas.js` desde el JSON tras cada actualización, así la web consume de verdad lo que el bot detecta. |
| `update-tools.yml` | Regenera y commitea también el JS; el paso FTP no rompe el flujo si faltan credenciales; sube JSON **y** JS a InfinityFree. |

## Cómo subirlo

### 1) A GitHub (repo `Viaje-a-taca-`)
Sube/reemplaza estos archivos respetando las rutas:

```
herramientas.json                      (raíz)
update_tools.py                        (raíz)
build_js.py                            (raíz, NUEVO)
data/herramientas.js                   (carpeta data/)
.github/workflows/update-tools.yml     (reemplaza el existente)
```

> Importante: **no** vuelvas a borrar y resubir `herramientas.json` a mano entre
> ejecuciones del bot; eso machaca lo que añade la automatización.

### 2) A InfinityFree (vía FTP, carpeta `htdocs/`)
- `data/herramientas.js`  → `htdocs/data/herramientas.js`
- `herramientas.json`     → `htdocs/data/herramientas.json`

(Si configuras los secrets FTP en GitHub, el workflow los subirá solo.)

## Secrets necesarios en GitHub (Settings → Secrets → Actions)
- `ITACA` → tu API key de Gemini (imprescindible para detectar bien).
- `FTP_HOST`, `FTP_USER`, `FTP_PASS` → opcionales; si están, sube a InfinityFree solo.

## Cómo comprobar que funciona
1. En GitHub → pestaña **Actions** → workflow "Actualizar herramientas IA" → **Run workflow** con `modo_prueba = 1`.
   - Debe añadir una "Herramienta de Prueba" al JSON (se excluye del JS público).
2. Ejecútalo con `modo_prueba = 0`. Si la clave Gemini está bien, en el log verás las herramientas detectadas; si algo falla, saldrá un aviso rojo/amarillo (ya no se queda "verde en silencio").
3. En la web, abre la consola del navegador (F12). Verás mensajes `🧭 ...`:
   - "Catálogo actualizado desde ..." cuando hay novedades.
   - "Sin novedades" cuando no las hay.
