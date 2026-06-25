/* ============================================================
 *  VIAJE A ÍTACA — Barra lateral de noticias de IA
 *  Autoinyectable: basta con <script src="barra-noticias.js" defer></script>
 *  Lee data/noticias.json (lo genera el workflow) y, si falla,
 *  intenta el raw de GitHub. No necesita tocar el HTML.
 * ============================================================ */
(function () {
  'use strict';

  var FUENTES = [
    'data/noticias.json',
    'https://raw.githubusercontent.com/naimmeliana-prog/Viaje-a-taca-/main/noticias.json'
  ];
  var REFRESCO = 1800000; // 30 min

  // ── Estilos (paleta de la web, inline para funcionar sin CSS externo) ──
  var css = `
  :root{
    --bn-mar:#1a5c7a; --bn-mar-claro:#2980b9; --bn-profundo:#0d3b56;
    --bn-atardecer:#e8985e; --bn-arena:#fdf6ec; --bn-blanco:#fffef9;
    --bn-borde:#e0d8c8; --bn-texto:#2c2c2c; --bn-texto-claro:#555;
  }
  #bn-toggle{position:fixed;right:0;top:50%;transform:translateY(-50%);
    z-index:9998;background:var(--bn-mar);color:#fff;border:none;
    padding:14px 8px;border-radius:10px 0 0 10px;cursor:pointer;
    font-size:.78rem;letter-spacing:.5px;writing-mode:vertical-rl;
    box-shadow:0 4px 14px rgba(0,0,0,.18);transition:background .25s;opacity:.92;}
  #bn-toggle:hover{background:var(--bn-mar-claro);opacity:1;}
  #bn-sidebar{position:fixed;right:0;top:0;height:100vh;width:340px;max-width:88vw;
    background:var(--bn-arena);border-left:1px solid var(--bn-borde);
    box-shadow:-6px 0 24px rgba(0,0,0,.12);z-index:9999;
    transform:translateX(100%);transition:transform .3s ease;
    display:flex;flex-direction:column;font-family:inherit;}
  #bn-sidebar.abierta{transform:translateX(0);}
  /* Empuje del contenido: el body se desplaza a la izquierda cuando la barra
     está abierta (solo en pantallas anchas). En móvil se superpone. */
  body{transition:padding-right .3s ease;}
  body.bn-empuja{padding-right:340px;}
  @media(max-width:820px){
    body.bn-empuja{padding-right:0;}
  }
  .bn-head{background:linear-gradient(135deg,var(--bn-profundo),var(--bn-mar));
    color:#fff;padding:18px 16px 14px;}
  .bn-head h3{margin:0;font-size:1.05rem;display:flex;align-items:center;gap:8px;}
  .bn-head p{margin:4px 0 0;font-size:.72rem;opacity:.8;}
  .bn-cerrar{position:absolute;top:12px;right:12px;background:transparent;
    border:none;color:#fff;font-size:1.3rem;cursor:pointer;line-height:1;opacity:.85;}
  .bn-cerrar:hover{opacity:1;}
  .bn-tabs{display:flex;border-bottom:1px solid var(--bn-borde);background:var(--bn-blanco);}
  .bn-tab{flex:1;padding:11px 6px;border:none;background:transparent;cursor:pointer;
    font-size:.82rem;color:var(--bn-texto-claro);font-weight:600;
    border-bottom:3px solid transparent;transition:.2s;}
  .bn-tab.activa{color:var(--bn-mar);border-bottom-color:var(--bn-atardecer);}
  .bn-lista{overflow-y:auto;flex:1;padding:6px 0;}
  .bn-item{display:block;padding:12px 16px;border-bottom:1px solid var(--bn-borde);
    text-decoration:none;color:var(--bn-texto);transition:background .15s;}
  .bn-item:hover{background:#fff;}
  .bn-item .t{font-size:.88rem;line-height:1.35;font-weight:600;margin:0 0 5px;}
  .bn-item .m{font-size:.7rem;color:var(--bn-texto-claro);display:flex;
    justify-content:space-between;gap:8px;}
  .bn-item .m .medio{color:var(--bn-mar-claro);font-weight:600;}
  .bn-vacio{padding:24px 16px;color:var(--bn-texto-claro);font-size:.85rem;text-align:center;}
  .bn-foot{padding:9px 16px;font-size:.66rem;color:var(--bn-texto-claro);
    border-top:1px solid var(--bn-borde);background:var(--bn-blanco);text-align:center;}
  @media(max-width:480px){#bn-sidebar{width:300px;}}
  `;
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ── Estructura ──
  var toggle = document.createElement('button');
  toggle.id = 'bn-toggle';
  toggle.setAttribute('aria-label', 'Abrir noticias de IA');
  toggle.textContent = '📰 Bitácora IA';

  var aside = document.createElement('aside');
  aside.id = 'bn-sidebar';
  aside.setAttribute('aria-hidden', 'true');
  aside.innerHTML =
    '<div class="bn-head">' +
      '<button class="bn-cerrar" aria-label="Cerrar">&times;</button>' +
      '<h3>🧭 Novedades de IA</h3>' +
      '<p id="bn-actualizado">Cargando titulares…</p>' +
    '</div>' +
    '<div class="bn-tabs">' +
      '<button class="bn-tab activa" data-tab="novedades">✨ Novedades</button>' +
      '<button class="bn-tab" data-tab="etica">⚖️ Ética</button>' +
    '</div>' +
    '<div class="bn-lista" id="bn-lista"><div class="bn-vacio">Cargando…</div></div>' +
    '<div class="bn-foot">Actualizado automáticamente cada 2 días · Viaje a Ítaca</div>';

  function init() {
    document.body.appendChild(toggle);
    document.body.appendChild(aside);

    toggle.addEventListener('click', function () { abrir(false); });
    aside.querySelector('.bn-cerrar').addEventListener('click', cerrar);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });
    aside.querySelectorAll('.bn-tab').forEach(function (b) {
      b.addEventListener('click', function () { activarTab(b.dataset.tab); });
    });

    cargar();
    setInterval(cargar, REFRESCO);

    // Abierta por defecto al cargar (en pantallas anchas y si el usuario
    // no la había cerrado expresamente antes). En móvil empieza plegada
    // para no tapar el contenido.
    var cerradaAntes = false;
    try { cerradaAntes = localStorage.getItem('bn-cerrada') === '1'; } catch (e) {}
    if (window.innerWidth > 820 && !cerradaAntes) {
      abrir(true);
    }
  }

  function abrir(silencioso) {
    aside.classList.add('abierta');
    aside.setAttribute('aria-hidden', 'false');
    document.body.classList.add('bn-empuja');
    if (!silencioso) { try { localStorage.removeItem('bn-cerrada'); } catch (e) {} }
  }
  function cerrar() {
    aside.classList.remove('abierta');
    aside.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('bn-empuja');
    try { localStorage.setItem('bn-cerrada', '1'); } catch (e) {}
  }

  var datos = { novedades: [], etica: [] };
  var tabActiva = 'novedades';

  function activarTab(t) {
    tabActiva = t;
    aside.querySelectorAll('.bn-tab').forEach(function (b) {
      b.classList.toggle('activa', b.dataset.tab === t);
    });
    pintar();
  }

  function fechaCorta(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d)) return '';
    return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
  }

  function pintar() {
    var lista = aside.querySelector('#bn-lista');
    var items = datos[tabActiva] || [];
    if (!items.length) {
      lista.innerHTML = '<div class="bn-vacio">Sin titulares por ahora. Vuelve pronto. 🌊</div>';
      return;
    }
    lista.innerHTML = items.map(function (x) {
      var medio = x.medio ? '<span class="medio">' + esc(x.medio) + '</span>' : '<span></span>';
      var f = fechaCorta(x.fecha);
      return '<a class="bn-item" href="' + esc(x.enlace) + '" target="_blank" rel="noopener">' +
        '<p class="t">' + esc(x.titulo) + '</p>' +
        '<div class="m">' + medio + '<span>' + f + '</span></div>' +
      '</a>';
    }).join('');
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function cargar(idx) {
    idx = idx || 0;
    if (idx >= FUENTES.length) return;
    fetch(FUENTES[idx] + '?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (d) {
        datos.novedades = d.novedades || [];
        datos.etica = d.etica || [];
        var act = aside.querySelector('#bn-actualizado');
        var f = fechaCorta(d.actualizado);
        act.textContent = f ? ('Última actualización: ' + f) : 'Titulares recientes';
        pintar();
      })
      .catch(function () { cargar(idx + 1); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
