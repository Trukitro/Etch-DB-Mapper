/* API simulada: SOLO para desarrollo en un navegador normal (sin pywebview).
   Misma forma que core/api.py. Datos 100 % ficticios.
   Uso:  python -m http.server 8765   (en la raíz del repo)  ->  http://localhost:8765/webui/index.html */
(function () {
  'use strict';

  /* ---------- esquema de ejemplo (tienda) ---------- */
  const T = (name, cols, rels) => ({ name, schema: '', cols, rels: rels || [] });
  const c = (name, type, pk, nullable) => ({ name, type, pk: !!pk, null: !!nullable });

  const DEMO = [
    T('countries', [c('country_code', 'varchar(2)', 1), c('name', 'varchar(80)')]),
    T('customers', [c('customer_id', 'int', 1), c('email', 'varchar(120)'), c('full_name', 'varchar(120)'), c('created_at', 'datetime', 0, 1)]),
    T('addresses', [c('address_id', 'int', 1), c('customer_id', 'int'), c('country_code', 'varchar(2)'), c('street', 'varchar(160)'), c('city', 'varchar(80)')],
      [['customer_id', 'customers', 'customer_id'], ['country_code', 'countries', 'country_code']]),
    T('categories', [c('category_id', 'int', 1), c('name', 'varchar(80)'), c('parent_id', 'int', 0, 1)], [['parent_id', 'categories', 'category_id']]),
    T('suppliers', [c('supplier_id', 'int', 1), c('name', 'varchar(120)'), c('country_code', 'varchar(2)', 0, 1)], [['country_code', 'countries', 'country_code']]),
    T('products', [c('product_id', 'int', 1), c('sku', 'varchar(40)'), c('name', 'varchar(120)'), c('category_id', 'int'), c('price', 'decimal(10,2)')], [['category_id', 'categories', 'category_id']]),
    T('product_suppliers', [c('product_id', 'int', 1), c('supplier_id', 'int', 1), c('cost', 'decimal(10,2)')], [['product_id', 'products', 'product_id'], ['supplier_id', 'suppliers', 'supplier_id']]),
    T('orders', [c('order_id', 'int', 1), c('customer_id', 'int'), c('status', 'varchar(20)'), c('placed_at', 'datetime')], [['customer_id', 'customers', 'customer_id']]),
    T('order_items', [c('order_id', 'int', 1), c('product_id', 'int', 1), c('qty', 'int'), c('unit_price', 'decimal(10,2)')], [['order_id', 'orders', 'order_id'], ['product_id', 'products', 'product_id']]),
    T('payments', [c('payment_id', 'int', 1), c('order_id', 'int'), c('amount', 'decimal(10,2)'), c('method', 'varchar(20)')], [['order_id', 'orders', 'order_id']]),
    T('shipments', [c('shipment_id', 'int', 1), c('order_id', 'int'), c('carrier', 'varchar(40)', 0, 1)], [['order_id', 'orders', 'order_id']]),
    T('reviews', [c('review_id', 'int', 1), c('product_id', 'int'), c('rating', 'int'), c('body', 'text', 0, 1)], [['product_id', 'products', 'product_id']]),
    T('coupons', [c('coupon_id', 'int', 1), c('code', 'varchar(30)'), c('percent_off', 'int')]),
    T('audit_log', [c('id', 'int', 1), c('happened_at', 'datetime'), c('actor', 'varchar(60)', 0, 1), c('action', 'varchar(60)'), c('detail', 'text', 0, 1)]),
    T('app_settings', [c('key', 'varchar(60)', 1), c('value', 'text', 0, 1)]),
    T('newsletter_queue', [c('email', 'varchar(120)'), c('subject', 'varchar(160)', 0, 1), c('queued_at', 'datetime', 0, 1)]),
  ];

  /* ---------- generador "base grande": 171 tablas / ~1970 columnas / 44 FK / 121 huérfanas ---------- */
  function stress() {
    let seed = 7;
    const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
    const pick = (a) => a[Math.floor(rnd() * a.length)];
    const prefixes = ['tbl', 'ETS', 'Cat', 'Sys', 'Cfg', 'Rpt', 'Tmp', 'Log'];
    const nouns = ['Customer', 'Order', 'Invoice', 'Payment', 'Shipment', 'Driver', 'Vehicle', 'Route', 'Contract', 'Rate', 'Zone', 'Stop', 'Note', 'User', 'Role', 'Permission', 'Document', 'Event', 'Status', 'Branch', 'Account', 'Address', 'Phone', 'Email', 'Schedule', 'Fee'];
    const types = ['int', 'varchar(50)', 'varchar(255)', 'datetime', 'bit', 'decimal(18,2)', 'nvarchar(100)', 'bigint', 'text'];
    const used = new Set(), out = [];
    const name = () => { for (;;) { const n = pick(prefixes) + '_' + pick(nouns) + (rnd() < 0.55 ? pick(nouns) : '') + (rnd() < 0.25 ? 's' : ''); if (!used.has(n)) { used.add(n); return n; } } };
    for (let i = 0; i < 171; i++) {
      const n = name(), idc = n.split('_')[1] + 'ID';
      const cols = [c(idc, 'int', 1)];
      const extra = i < 150 ? 9 + Math.floor(rnd() * 5) : 14 + Math.floor(rnd() * 8);
      for (let k = 0; k < extra; k++) cols.push(c(pick(nouns) + pick(['Name', 'Code', 'Date', 'Flag', 'Amount', 'Notes', 'Ref']) + (k % 3 ? '' : k), pick(types), 0, rnd() < 0.6));
      out.push(T(n, cols));
    }
    // 44 FKs repartidas en ~50 tablas (3 grupos), el resto queda huérfano
    const relatedIdx = Array.from({ length: 50 }, (_, i) => i);
    const groups = [relatedIdx.slice(0, 22), relatedIdx.slice(22, 38), relatedIdx.slice(38, 50)];
    let fks = 0;
    groups.forEach((g) => {
      const hubs = g.slice(0, 3);
      g.slice(3).forEach((i) => {
        if (fks >= 44) return;
        const hub = pick(hubs), parent = out[hub];
        out[i].rels.push([`${parent.cols[0].name}`, parent.name, parent.cols[0].name]); fks++;
        out[i].cols.push(c(parent.cols[0].name, 'int'));
      });
    });
    for (let extra = 0; fks < 44; extra++) {
      const g = groups[extra % 3], a = out[pick(g.slice(3))], b = out[pick(g.slice(0, 3))];
      if (a === b || a.rels.some((r) => r[1] === b.name)) continue;
      a.rels.push([b.cols[0].name + '2', b.name, b.cols[0].name]); a.cols.push(c(b.cols[0].name + '2', 'int', 0, 1)); fks++;
    }
    return out;
  }

  /* ---------- helpers ---------- */
  function toRaw(list) {
    const t = {};
    list.forEach((x) => { t[x.name] = { schema: x.schema, name: x.name, columns: x.cols, relations: x.rels.map((r) => ({ col: r[0], ref_table: r[1], ref_col: r[2] })) }; });
    return t;
  }
  function finalize(raw) {
    const out = {};
    for (const [n, t] of Object.entries(raw)) {
      const fkc = new Set(t.relations.map((r) => r.col));
      out[n] = { schema: t.schema, name: t.name, relations: t.relations, referenced_by: [],
        columns: t.columns.map((x) => ({ name: x.name, type: x.type, null: !!x.null, pk: !!x.pk, fk: fkc.has(x.name) })) };
    }
    for (const [n, t] of Object.entries(out)) t.relations.forEach((r) => { if (out[r.ref_table]) out[r.ref_table].referenced_by.push({ table: n, col: r.col, ref_col: r.ref_col }); });
    return out;
  }
  function metaOf(t) {
    const names = Object.keys(t), related = names.filter((n) => t[n].relations.length || t[n].referenced_by.length);
    return { table_count: names.length, column_count: names.reduce((s, n) => s + t[n].columns.length, 0),
      relation_count: names.reduce((s, n) => s + t[n].relations.length, 0), related_count: related.length,
      orphan_count: names.length - related.length, no_pk_count: names.filter((n) => !t[n].columns.some((x) => x.pk)).length };
  }
  const now = () => new Date().toISOString().slice(0, 19).replace('T', ' ');
  const engineOf = (uri) => { const m = /^([a-z0-9]+)/i.exec(uri || ''); if (!m) return null; const p = m[1].toLowerCase(); return p.startsWith('postgres') ? 'postgres' : p.startsWith('mssql') ? 'mssql' : p.startsWith('mysql') ? 'mysql' : p.startsWith('sqlite') ? 'sqlite' : p; };
  const mask = (u) => (u || '').replace(/^([a-zA-Z0-9:+]+:\/\/)([^:/@]+):(.*)@/, '$1$2:••••@');
  const emit = (e, p) => window.EtchBridge && window.EtchBridge.emit(e, p);

  /* ---------- estado en memoria ---------- */
  const store = {};
  const scans = {};
  let nextId = 1;
  function put(alias, uri, data) {
    store[alias] = { id: 'c' + nextId++, uri, status: data ? 'success' : 'pending', data: data || {}, last_scan: data ? now() : null, duration_sec: data ? 0.42 : 0, last_error: null, map: {} };
  }
  put('Tienda demo', 'sqlite://C:/demo/tienda.sqlite', toRaw(DEMO));
  put('Base grande (171 tablas)', 'mssql4://usuario:secreto@srv-ejemplo:1433/BaseGrande?DRIVER={SQL Server}', toRaw(stress()));
  put('Servidor caído', 'postgres://usuario:clave@192.0.2.10:5432/prueba', null);
  store['Servidor caído'].status = 'error';
  store['Servidor caído'].last_error = 'No se pudo conectar a 192.0.2.10:5432 (tiempo de espera agotado). Revisá host, puerto y firewall.';

  const summary = (alias) => {
    const e = store[alias], t = e.data && Object.keys(e.data).length ? finalize(e.data) : {}, m = metaOf(t), s = scans[e.id];
    return { id: e.id, alias, engine: engineOf(e.uri), masked_uri: mask(e.uri), status: e.status, last_scan: e.last_scan, duration_sec: e.duration_sec,
      last_error: e.last_error, table_count: m.table_count, relation_count: m.relation_count, has_data: !!Object.keys(e.data).length, scan: s ? { ...s } : null };
  };
  const list = () => Object.keys(store).map(summary);
  const delay = (ms, v) => new Promise((r) => setTimeout(() => r(v), ms));
  const checkAlias = (a) => (!a ? 'Poné un nombre para la conexión.' : a.length > 60 ? 'El nombre es demasiado largo (máximo 60 caracteres).' : null);

  /* ---------- API ---------- */
  window.EtchMockApi = {
    async bootstrap() {
      return { app_name: 'Etch-DB-Mapper', version: '2.0.0', repo_url: 'https://github.com/Trukitro/Etch-DB-Mapper', platform: 'dev',
        data_dir: '(modo desarrollo: datos simulados en memoria)', settings: { theme: localStorage.getItem('etch-dev-theme') || 'dark', sidebar_collapsed: false, map_layout: 'fcose', map_include_orphans: false, last_alias: '', seen_version: '2.0.0' },
        connections: list(), warnings: [] };
    },
    async save_settings(p) { if (p && p.theme) { try { localStorage.setItem('etch-dev-theme', p.theme); } catch (e) { /* nada */ } } return { ok: true, settings: p }; },
    async get_changelog() { return fetch('../CHANGELOG.md').then((r) => r.text()).then((markdown) => ({ ok: true, markdown })).catch(() => ({ ok: true, markdown: '# Novedades\n\n(sin CHANGELOG en modo desarrollo)' })); },
    async get_help() { return fetch('../HELP.md').then((r) => r.text()).then((markdown) => ({ ok: true, markdown })).catch(() => ({ ok: true, markdown: '# Ayuda\n\n(sin HELP en modo desarrollo)' })); },
    async open_external(url) { window.open(url, '_blank', 'noopener'); return { ok: true }; },
    async log_js() { return { ok: true }; },
    async list_connections() { return list(); },
    async check_uri(uri) {
      const engine = engineOf(uri), native = ['postgres', 'mssql', 'mysql', 'sqlite'].includes(engine);
      return { engine, reader: engine ? (native ? 'native' : 'generic') : null, driver_error: engine === 'mysql' ? 'Falta el driver de MySQL: pip install pymysql' : null };
    },
    async get_connection(alias) { return store[alias] ? { ok: true, alias, uri: store[alias].uri } : { ok: false, error: 'La conexión ya no existe.' }; },
    async save_connection(alias, uri, previous) {
      alias = (alias || '').trim(); uri = (uri || '').trim();
      const err = checkAlias(alias); if (err) return { ok: false, error: err };
      if (!uri.includes('://')) return { ok: false, error: 'La URI debe tener la forma motor://usuario:clave@host:puerto/base' };
      if (previous && store[previous]) {
        if (alias !== previous) { if (store[alias]) return { ok: false, error: `Ya existe una conexión llamada '${alias}'.` }; store[alias] = store[previous]; delete store[previous]; }
        if (store[alias].uri !== uri) { store[alias].uri = uri; store[alias].status = 'pending'; store[alias].last_error = null; }
      } else if (store[alias]) return { ok: false, error: `Ya existe una conexión llamada '${alias}'. Editala desde la barra lateral.` };
      else put(alias, uri, null);
      return { ok: true, alias, connection: summary(alias) };
    },
    async rename_connection(oldName, newName) {
      newName = (newName || '').trim();
      const err = checkAlias(newName); if (err) return { ok: false, error: err };
      if (!store[oldName]) return { ok: false, error: 'La conexión ya no existe.' };
      if (store[newName]) return { ok: false, error: `Ya existe una conexión llamada '${newName}'.` };
      store[newName] = store[oldName]; delete store[oldName];
      return { ok: true, alias: newName, connections: list() };
    },
    async delete_connection(alias) { delete store[alias]; return { ok: true, connections: list() }; },
    async create_demo_connection() { if (!store['Tienda de ejemplo']) put('Tienda de ejemplo', 'sqlite://C:/demo/tienda.sqlite', null); return { ok: true, alias: 'Tienda de ejemplo', connection: summary('Tienda de ejemplo') }; },
    async start_scan(alias) {
      const e = store[alias]; if (!e) return { ok: false, error: 'La conexión ya no existe.' };
      const gen = (scans[e.id] = { gen: Math.random(), phase: 'connect', message: 'Conectando…', pct: 5, started: Date.now() / 1000 });
      e.status = 'pending'; e.last_error = null;
      emit('scan_started', { alias, id: e.id });
      const fail = /caido|caído|fail|broken/i.test(alias) || /192\.0\.2\.10/.test(e.uri);
      const steps = [['connect', 'Conectando…', 5], ['tables', 'Leyendo tablas…', 25], ['columns', 'Leyendo columnas (1972)…', 55], ['keys', 'Leyendo claves…', 75], ['relations', 'Leyendo relaciones…', 88], ['build', 'Armando el esquema…', 92]];
      let i = 0;
      const tick = () => {
        if (scans[e.id] !== gen) return;
        if (fail && i === 2) {
          delete scans[e.id]; e.status = 'error'; e.last_error = 'No se pudo conectar a 192.0.2.10:5432 (tiempo de espera agotado). Revisá host, puerto y firewall.';
          emit('scan_finished', { alias, id: e.id, ok: false, message: e.last_error, connection: summary(alias) }); return;
        }
        if (i >= steps.length) {
          delete scans[e.id];
          if (!Object.keys(e.data).length) e.data = toRaw(DEMO);
          e.status = 'success'; e.last_scan = now(); e.duration_sec = 2.4;
          emit('scan_finished', { alias, id: e.id, ok: true, message: null, connection: summary(alias) }); return;
        }
        const [phase, message, pct] = steps[i++];
        Object.assign(gen, { phase, message, pct });
        emit('scan_progress', { alias, id: e.id, phase, message, pct });
        setTimeout(tick, 450);
      };
      setTimeout(tick, 250);
      return { ok: true };
    },
    async get_schema(alias) {
      const e = store[alias]; if (!e) return { ok: false, error: 'La conexión ya no existe.' };
      await delay(80);
      const tables = finalize(e.data);
      return { ok: true, alias, engine: engineOf(e.uri), status: e.status, last_scan: e.last_scan, duration_sec: e.duration_sec, last_error: e.last_error, tables, meta: metaOf(tables), map: e.map || {} };
    },
    async save_map_state(alias, state) { if (store[alias]) store[alias].map = state; return { ok: !!store[alias] }; },
    async pick_file() { return { ok: false }; },
    async save_file(name, content, encoding) {
      const blob = encoding === 'base64' ? new Blob([Uint8Array.from(atob(content), (ch) => ch.charCodeAt(0))]) : new Blob([content], { type: 'text/plain' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click(); a.remove();
      return { ok: true, path: name + ' (descargado)' };
    },
  };
})();
