/* Orquestación: estado global, enrutador, tema, escaneo y atajos de teclado. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon, $, clear } = Etch;

  const CONN_VIEWS = ['overview', 'explorer', 'map', 'changes'];
  const FILL_VIEWS = ['explorer', 'map'];
  const TAB_DEFS = [
    ['overview', 'Resumen', 'grid'],
    ['explorer', 'Explorador', 'table'],
    ['map', 'Mapa', 'map'],
    ['changes', 'Cambios', 'history'],
  ];
  const PHASES = [['connect', 'Conectar'], ['tables', 'Tablas'], ['columns', 'Columnas'], ['keys', 'Claves'], ['relations', 'Relaciones'], ['build', 'Armar']];

  const S = (Etch.state = {
    version: '', repoUrl: '', platform: '', dataDir: '',
    settings: { theme: 'dark', sidebar_collapsed: false, map_layout: 'fcose', map_include_orphans: false, last_alias: '', seen_version: '' },
    connections: [],
    alias: null, view: 'home', args: {},
    schema: null, schemaAlias: null, schemaLoading: false,
    update: null, updateBlocked: false,
  });
  let mounted = null;

  const conn = (alias) => S.connections.find((c) => c.alias === (alias || S.alias)) || null;
  Etch.conn = conn;

  /* ---------------- tema ---------------- */
  const mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function resolvedTheme() {
    const t = S.settings.theme;
    return t === 'system' ? (mql && mql.matches ? 'dark' : 'light') : (t === 'light' ? 'light' : 'dark');
  }
  function applyTheme() {
    document.documentElement.setAttribute('data-theme', resolvedTheme());
    if (mounted && mounted.onTheme) mounted.onTheme();
  }
  if (mql && mql.addEventListener) mql.addEventListener('change', () => { if (S.settings.theme === 'system') applyTheme(); });
  Etch.applyTheme = applyTheme;
  Etch.cycleTheme = function () {
    const order = ['dark', 'light', 'system'];
    S.settings.theme = order[(order.indexOf(S.settings.theme) + 1) % order.length];
    applyTheme(); renderChrome();
    Etch.api.save_settings({ theme: S.settings.theme });
  };
  Etch.toggleSidebar = function () {
    S.settings.sidebar_collapsed = !S.settings.sidebar_collapsed;
    renderChrome();
    Etch.api.save_settings({ sidebar_collapsed: S.settings.sidebar_collapsed });
  };
  Etch.saveSetting = function (key, value) {
    S.settings[key] = value;
    return Etch.api.save_settings({ [key]: value });
  };

  /* ---------------- versión nueva ---------------- */
  Etch.setUpdate = function (info) { S.update = info; renderChrome(); };
  function checkUpdatesLater() {
    if (S.updateBlocked || !S.settings.check_updates) return;
    setTimeout(async () => {
      try {
        const r = await Etch.api.check_updates(false);
        if (r && r.ok && r.newer) {
          Etch.setUpdate(r);
          Etch.toast('info', 'Hay una versión nueva: ' + r.latest, { detail: 'Tienes la ' + r.current + '. Mira el aviso en la barra lateral.', timeout: 8000 });
        }
      } catch (e) { /* sin red: no pasa nada */ }
    }, 4000);
  }

  /* ---------------- render ---------------- */
  function renderTopbar() {
    const bar = clear($('#topbar'));
    const c = conn();
    if (CONN_VIEWS.includes(S.view) && c) {
      const busy = !!c.scan;
      let sub;
      if (busy) sub = h('span', { style: { color: 'var(--accent)' } }, c.scan.message || 'Escaneando…');
      else if (c.status === 'error' && c.has_data) sub = h('span', { style: { color: 'var(--bad)' } }, 'El último escaneo falló — se muestran los datos anteriores');
      else if (c.has_data) sub = h('span', null, Etch.engineLabel(c.engine) + ' · ' + Etch.plural(c.table_count, 'tabla', 'tablas') + ' · escaneado ' + Etch.relTime(c.last_scan));
      else sub = h('span', null, Etch.engineLabel(c.engine) + ' · sin escanear');
      bar.append(
        h('div', { style: { minWidth: 0 } }, h('div', { class: 'crumb truncate' }, c.alias), h('div', { class: 'sub truncate' }, sub)),
        c.has_data ? h('div', { class: 'tabs', role: 'tablist' }, TAB_DEFS.map(([id, label, ic], i) =>
          h('button', { class: 'tab', role: 'tab', 'aria-selected': String(S.view === id), title: label + ' (Alt+' + (i + 1) + ')',
            onclick: () => Etch.go(id) }, icon(ic, 15), label))) : null,
        h('div', { class: 'grow' }),
        h('button', { class: 'btn', disabled: busy, onclick: () => Etch.scan(c.alias), title: 'Reescanear (F5)' },
          icon('refresh', 16), busy ? 'Escaneando…' : 'Reescanear'),
        h('button', { class: 'btn icon-only ghost', title: 'Editar conexión', 'aria-label': 'Editar conexión', onclick: () => Etch.dialogs.connection({ alias: c.alias }) }, icon('edit', 16)));
    } else {
      const title = S.view === 'help' ? 'Ayuda' : S.view === 'changelog' ? 'Novedades' : 'Inicio';
      bar.append(h('div', { class: 'crumb' }, title), h('div', { class: 'grow' }),
        h('span', { class: 'faint', style: { fontSize: '12px' } }, 'Etch-DB-Mapper v' + S.version));
    }
    $('#scanbar').hidden = !(CONN_VIEWS.includes(S.view) && c && c.scan);
  }

  function renderChrome() { Etch.renderSidebar(); renderTopbar(); }

  function unmount() {
    if (mounted && mounted.destroy) { try { mounted.destroy(); } catch (e) { console.error(e); } }
    mounted = null;
  }

  function scanCard(c) {
    const sc = c.scan;
    const idx = Math.max(0, PHASES.findIndex((p) => p[0] === sc.phase));
    return h('div', { class: 'page' }, h('div', { class: 'card scan-card', 'data-scan-card': c.alias },
      h('div', { class: 'spinner' }),
      h('h2', { style: { margin: '0 0 4px' } }, 'Escaneando «' + c.alias + '»'),
      h('div', { class: 'muted', 'data-scan-text': '' }, sc.message || 'Conectando…'),
      h('div', { class: 'phases', 'data-scan-phases': '' }, PHASES.map((p, i) => h('span', { class: 'phase' + (i < idx ? ' done' : i === idx ? ' now' : '') }, p[1]))),
      h('div', { class: 'meter' }, h('span', { 'data-scan-meter': '', style: { width: Math.max(4, sc.pct || 0) + '%' } })),
      h('div', { class: 'faint', style: { fontSize: '12.5px' } }, 'Tiempo: ', h('span', { 'data-elapsed': c.alias }, '0 s')),
      h('p', { class: 'faint', style: { fontSize: '12.5px', margin: '14px 0 0' } }, 'El escaneo corre en segundo plano: podés seguir usando la app. Las bases grandes pueden tardar un poco.')));
  }

  function stateCard(c) {
    const failed = c.status === 'error';
    return h('div', { class: 'page' }, h('div', { class: 'card', style: { maxWidth: '680px', margin: '40px auto' } },
      h('div', { class: 'row', style: { gap: '12px', marginBottom: '10px' } },
        h('span', { style: { color: failed ? 'var(--bad)' : 'var(--accent)' } }, icon(failed ? 'alert' : 'database', 28)),
        h('h2', { style: { margin: 0 } }, failed ? 'No se pudo leer el esquema' : 'Esta conexión todavía no se escaneó')),
      h('p', { class: 'muted', style: { margin: '0 0 12px' } }, failed
        ? 'La conexión sigue guardada, no hace falta volver a escribirla. Revisá el detalle, corregí la URI si hace falta y reintentá.'
        : 'La conexión está guardada. Escaneala para leer sus tablas, columnas y relaciones.'),
      c.secret_error ? h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, h('b', null, 'No se pudo descifrar la contraseña. '),
        'La conexión se guardó con otro usuario de Windows u otro equipo. Edítala y vuelve a escribir la contraseña.')) : null,
      failed && c.last_error ? h('pre', { class: 'mono', style: { whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '10px', padding: '12px', margin: '0 0 12px', fontSize: '12.5px', color: 'var(--bad)' } }, c.last_error) : null,
      h('div', { class: 'faint mono truncate', style: { marginBottom: '14px', fontSize: '12px' }, title: c.masked_uri }, c.masked_uri),
      h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '8px' } },
        h('button', { class: 'btn primary', onclick: () => Etch.scan(c.alias) }, icon(failed ? 'refresh' : 'play', 16), failed ? 'Reintentar' : 'Escanear ahora'),
        h('button', { class: 'btn', onclick: () => Etch.dialogs.connection({ alias: c.alias }) }, icon('edit', 16), 'Editar conexión'),
        failed && c.last_error ? h('button', { class: 'btn', onclick: async () => { await Etch.copyText(c.last_error); Etch.toast('info', 'Error copiado', { timeout: 1800 }); } }, icon('copy', 16), 'Copiar error') : null,
        failed ? h('button', { class: 'btn ghost', onclick: () => Etch.go('help', { anchor: 'solucion-de-problemas' }) }, icon('help', 16), 'Ver ayuda') : null)));
  }

  function loadingView() {
    return h('div', { class: 'page' }, h('div', { class: 'skeleton', style: { height: '28px', width: '220px', marginBottom: '18px' } }),
      h('div', { class: 'grid stats' }, [0, 1, 2, 3].map(() => h('div', { class: 'skeleton', style: { height: '98px' } }))),
      h('div', { class: 'skeleton', style: { height: '260px' } }));
  }

  function renderView() {
    unmount();
    const root = clear($('#view'));
    root.className = 'view';
    const c = conn();
    let key = S.view;
    if (CONN_VIEWS.includes(key) && !c) key = 'home';

    if (CONN_VIEWS.includes(key)) {
      if (c.scan && !c.has_data) { root.append(scanCard(c)); return; }
      if (!c.has_data) { root.append(stateCard(c)); return; }
      if (S.schemaAlias !== c.alias || !S.schema) { root.append(loadingView()); loadSchema(c.alias); return; }
    }
    const view = Etch.views[key];
    if (!view) { root.append(h('div', { class: 'page' }, 'Vista desconocida: ' + key)); return; }
    if (FILL_VIEWS.includes(key)) root.classList.add('fill');
    root.scrollTop = 0;
    view.render(root, S.args || {});
    mounted = view;
  }

  Etch.render = function () { renderChrome(); renderView(); };
  Etch.renderChrome = renderChrome;

  /* ---------------- navegación ---------------- */
  Etch.go = function (view, args) {
    if (CONN_VIEWS.includes(view) && !conn()) view = 'home';
    S.view = view; S.args = args || {};
    Etch.render();
  };
  Etch.openTable = function (name) { Etch.go('explorer', { table: name }); };

  Etch.selectConnection = function (alias) {
    if (!conn(alias)) return;
    if (S.alias !== alias) { S.alias = alias; S.schema = null; S.schemaAlias = null; }
    Etch.saveSetting('last_alias', alias);
    S.view = CONN_VIEWS.includes(S.view) ? S.view : 'overview';
    S.args = {};
    Etch.render();
  };

  Etch.refreshConnections = async function () {
    S.connections = (await Etch.api.list_connections()) || [];
    if (S.alias && !conn()) { S.alias = null; S.schema = null; S.schemaAlias = null; if (CONN_VIEWS.includes(S.view)) S.view = 'home'; }
  };

  async function loadSchema(alias) {
    if (S.schemaLoading) return;
    S.schemaLoading = true;
    try {
      const r = await Etch.api.get_schema(alias);
      if (S.alias !== alias) return;
      if (!r.ok) { Etch.toast('error', r.error); return; }
      S.schema = r; S.schemaAlias = alias;
    } catch (e) {
      Etch.toast('error', 'No se pudo cargar el esquema', { detail: String(e && e.message || e) });
      return;
    } finally { S.schemaLoading = false; }
    if (CONN_VIEWS.includes(S.view) && S.alias === alias) renderView();
  }

  Etch.deleteConnection = async function (alias) {
    const ok = await Etch.dialogs.confirm({
      title: 'Eliminar conexión', danger: true, confirmLabel: 'Eliminar',
      message: '«' + alias + '» se borrará de este equipo junto con su esquema escaneado y las posiciones del mapa. La base de datos real no se toca.',
    });
    if (!ok) return;
    const r = await Etch.api.delete_connection(alias);
    S.connections = r.connections || [];
    if (S.alias === alias) { S.alias = null; S.schema = null; S.schemaAlias = null; if (CONN_VIEWS.includes(S.view)) S.view = 'home'; }
    Etch.render();
    Etch.toast('success', 'Conexión eliminada', { detail: alias, timeout: 2800 });
  };

  /* ---------------- escaneo ---------------- */
  Etch.scan = async function (alias) {
    const c = conn(alias);
    if (!c || c.scan) return;
    const r = await Etch.api.start_scan(alias);
    if (!r.ok) Etch.toast('error', r.error || 'No se pudo iniciar el escaneo');
    // El estado "escaneando" llega con el evento scan_started (el escaneo puede terminar antes de que vuelva esta respuesta).
  };

  function markScanning(alias) {
    const c = conn(alias);
    if (!c) return;
    if (!c.scan) c.scan = { phase: 'connect', message: 'Conectando…', pct: 0, started: Date.now() / 1000 };
    Etch.render();
  }

  function updateScanUI(c) {
    document.querySelectorAll('[data-scan-msg]').forEach((el) => { if (el.getAttribute('data-scan-msg') === c.alias) el.textContent = c.scan.message || 'Escaneando…'; });
    if (S.alias !== c.alias) return;
    const sub = document.querySelector('#topbar .sub span');
    if (sub && c.scan) sub.textContent = c.scan.message || 'Escaneando…';
    const card = document.querySelector('[data-scan-card]');
    if (!card) return;
    card.querySelector('[data-scan-text]').textContent = c.scan.message || '';
    card.querySelector('[data-scan-meter]').style.width = Math.max(4, c.scan.pct || 0) + '%';
    const idx = Math.max(0, PHASES.findIndex((p) => p[0] === c.scan.phase));
    card.querySelectorAll('.phase').forEach((el, i) => { el.className = 'phase' + (i < idx ? ' done' : i === idx ? ' now' : ''); });
  }

  Etch.on('scan_started', (e) => markScanning(e.alias));
  Etch.on('scan_progress', (e) => {
    const c = conn(e.alias);
    if (!c) return;
    if (!c.scan) { markScanning(e.alias); }
    Object.assign(c.scan, { phase: e.phase, message: e.message, pct: e.pct == null ? c.scan.pct : e.pct });
    updateScanUI(c);
  });
  Etch.on('scan_finished', async (e) => {
    const idx = S.connections.findIndex((c) => c.alias === e.alias);
    if (idx < 0) return;
    S.connections[idx] = e.connection;
    if (e.ok) {
      const c = e.connection;
      Etch.toast('success', 'Escaneo completo: ' + e.alias, { detail: Etch.plural(c.table_count, 'tabla', 'tablas') + ' · ' + Etch.plural(c.relation_count, 'relación', 'relaciones') + ' · ' + Etch.fmtDuration(c.duration_sec) });
      if (e.changes && e.changes.total > 0) {
        Etch.toast('warning', 'El esquema cambió desde el escaneo anterior', { detail: e.changes.text + '. Míralo en la pestaña Cambios.', timeout: 9000 });
      }
      if (S.alias === e.alias) { S.schema = null; S.schemaAlias = null; }
    } else {
      Etch.toast('error', 'No se pudo escanear «' + e.alias + '»', { detail: e.message || e.connection.last_error, timeout: 12000 });
    }
    if (S.alias === e.alias && e.ok && CONN_VIEWS.includes(S.view)) {
      const keepView = Etch.views[S.view];
      S.schemaLoading = false;
      renderChrome();
      // Recarga el esquema nuevo y vuelve a dibujar la vista (conserva pestaña actual).
      const r = await Etch.api.get_schema(e.alias);
      if (r.ok && S.alias === e.alias) { S.schema = r; S.schemaAlias = e.alias; }
      if (keepView) renderView();
    } else {
      Etch.render();
    }
  });

  setInterval(() => {
    document.querySelectorAll('[data-elapsed]').forEach((el) => {
      const c = conn(el.getAttribute('data-elapsed'));
      if (c && c.scan) el.textContent = Etch.fmtDuration(Math.max(0, Date.now() / 1000 - c.scan.started));
    });
  }, 250);

  /* ---------------- atajos ---------------- */
  const typing = (e) => /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || '')) || e.target.isContentEditable;
  Etch.focusSearch = function () {
    const c = conn();
    if (!c || !c.has_data) return;
    if (S.view === 'overview' || !CONN_VIEWS.includes(S.view)) Etch.go('explorer');
    setTimeout(() => { const el = $('#search-box'); if (el) { el.focus(); el.select(); } }, 30);
  };
  document.addEventListener('keydown', (e) => {
    if ($('#modal-root').childElementCount) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); Etch.focusSearch(); return; }
    if (mod && e.key.toLowerCase() === 'n') { e.preventDefault(); Etch.dialogs.connection(); return; }
    if (mod && e.key.toLowerCase() === 'b') { e.preventDefault(); Etch.toggleSidebar(); return; }
    if (e.key === 'F5' || (mod && e.key.toLowerCase() === 'r')) {
      e.preventDefault();
      if (S.alias) Etch.scan(S.alias);
      return;
    }
    if (e.altKey && ['1', '2', '3', '4'].includes(e.key)) {
      const c = conn();
      if (c && c.has_data) { e.preventDefault(); Etch.go(TAB_DEFS[Number(e.key) - 1][0]); }
      return;
    }
    if (typing(e)) return;
    if (e.key === '/') { e.preventDefault(); Etch.focusSearch(); }
    else if (e.key === '?') { e.preventDefault(); Etch.go('help', { anchor: 'atajos-de-teclado' }); }
  });

  /* ---------------- errores globales -> aviso ---------------- */
  let lastErrAt = 0;
  window.addEventListener('error', (e) => {
    if (Date.now() - lastErrAt < 3000) return;
    lastErrAt = Date.now();
    Etch.toast('error', 'Ocurrió un error inesperado en la interfaz', { detail: e.message });
  });

  /* ---------------- arranque ---------------- */
  async function init() {
    applyTheme();
    let boot;
    try {
      boot = await Etch.api.bootstrap();
    } catch (e) {
      $('#view').append(h('div', { class: 'page' }, h('div', { class: 'card' }, h('h2', null, 'No se pudo iniciar la aplicación'), h('pre', { class: 'mono' }, String(e && e.message || e)))));
      return;
    }
    Object.assign(S, { version: boot.version, repoUrl: boot.repo_url, platform: boot.platform, dataDir: boot.data_dir, updateBlocked: !!boot.update_check_blocked });
    Object.assign(S.settings, boot.settings);
    S.connections = boot.connections || [];
    applyTheme();

    // Enlaces externos: nunca navegar la ventana de la app; abrir en el navegador del sistema.
    document.addEventListener('click', (e) => {
      const a = e.target.closest && e.target.closest('a[href]');
      if (!a) return;
      const href = a.getAttribute('href');
      if (/^https?:/i.test(href)) { e.preventDefault(); Etch.api.open_external(href); }
      else if (href.startsWith('#')) {
        e.preventDefault();
        const t = document.getElementById(href.slice(1));
        if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });

    const last = S.settings.last_alias && conn(S.settings.last_alias) ? S.settings.last_alias : null;
    if (last) { S.alias = last; S.view = 'overview'; }
    Etch.render();

    (boot.warnings || []).forEach((w) => Etch.toast('warning', 'Aviso al cargar los datos', { detail: w, timeout: 15000 }));
    if (S.settings.seen_version !== S.version && S.connections.length) {
      Etch.toast('info', 'Etch-DB-Mapper se actualizó a v' + S.version, { detail: 'Mirá las novedades en la barra lateral.', timeout: 7000 });
    }
    if (S.settings.seen_version !== S.version) Etch.saveSetting('seen_version', S.version);
    checkUpdatesLater();
  }
  init();
})();
