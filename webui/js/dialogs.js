/* Diálogos modales: genérico + conexión (crear/editar), renombrar, confirmar. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon, $, debounce } = Etch;

  /* ---------------- modal genérico (con pila: Esc cierra solo el de arriba) ---------------- */
  const stack = [];
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && stack.length) { e.stopPropagation(); stack[stack.length - 1].close(); }
  }, true);

  function modal({ title, body, buttons, width, dismissible = true, onClose }) {
    const prevFocus = document.activeElement;
    const api = {
      close() {
        const i = stack.indexOf(api);
        if (i >= 0) stack.splice(i, 1);
        overlay.remove();
        if (prevFocus && prevFocus.focus) prevFocus.focus();
        if (onClose) onClose();
      },
    };
    const btnEls = (buttons || []).map((b) => h('button', {
      type: 'button', class: 'btn ' + (b.kind || ''),
      onclick: async () => { const keep = b.onClick ? await b.onClick(api) : undefined; if (keep !== false) api.close(); },
    }, b.icon ? icon(b.icon, 16) : null, b.label));
    api.buttons = btnEls;
    const box = h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': title, style: width ? { width } : null },
      h('header', null, h('h2', null, title),
        dismissible ? h('button', { class: 'btn icon-only ghost', 'aria-label': 'Cerrar', onclick: () => api.close() }, icon('x', 18)) : null),
      h('div', { class: 'body' }, body),
      h('footer', null, btnEls));
    const overlay = h('div', { class: 'overlay', onmousedown: (e) => { if (dismissible && e.target === overlay) api.close(); } }, box);
    api.el = box;
    $('#modal-root').append(overlay);
    stack.push(api);
    setTimeout(() => { const f = box.querySelector('[data-autofocus]') || box.querySelector('input,select'); if (f) f.focus(); }, 30);
    return api;
  }
  Etch.modal = modal;

  /* ---------------- confirmar ---------------- */
  Etch.dialogs.confirm = ({ title, message, confirmLabel = 'Aceptar', danger = false }) =>
    new Promise((resolve) => {
      let answered = false;
      const done = (v) => { answered = true; resolve(v); };
      modal({
        title, body: h('p', { class: 'muted', style: { margin: '4px 0 8px' } }, message),
        buttons: [
          { label: 'Cancelar', kind: 'ghost', onClick: () => done(false) },
          { label: confirmLabel, kind: danger ? 'danger solid' : 'primary', onClick: () => done(true) },
        ],
        onClose: () => { if (!answered) resolve(false); },
      });
    });

  /* ---------------- renombrar ---------------- */
  Etch.dialogs.rename = (alias) => {
    const input = h('input', { class: 'input', maxlength: 60, value: alias, spellcheck: 'false', 'data-autofocus': '' });
    const err = h('div', { class: 'hint bad', style: { minHeight: '18px' } });
    const submit = async () => {
      const name = input.value.trim();
      if (name === alias) return true;
      const r = await Etch.api.rename_connection(alias, name);
      if (!r.ok) { err.textContent = r.error; input.focus(); return false; }
      await Etch.refreshConnections();
      if (Etch.state.alias === alias) Etch.state.alias = r.alias;
      Etch.render();
      Etch.toast('success', 'Conexión renombrada', { detail: alias + ' → ' + r.alias, timeout: 2800 });
      return true;
    };
    const m = modal({
      title: 'Renombrar conexión', width: '460px',
      body: h('div', null,
        h('p', { class: 'muted', style: { margin: '0 0 12px' } }, 'El nombre es solo una etiqueta: la URI, el esquema escaneado y el mapa no cambian.'),
        h('div', { class: 'field' }, h('label', null, 'Nombre'), input), err),
      buttons: [{ label: 'Cancelar', kind: 'ghost' }, { label: 'Renombrar', kind: 'primary', onClick: submit }],
    });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') m.buttons[1].click(); });
    input.select();
  };

  /* ---------------- conexión (crear / editar) ----------------
     Dos modos que comparten la misma conexión:
       - Asistente: tipo de base + servidor, puerto, usuario, clave… (la URI se arma sola).
       - URI avanzada: el texto de pydal tal cual, para quien lo prefiere. */
  const ADV_TEMPLATES = [
    { id: 'postgres', label: 'PostgreSQL', tpl: 'postgres://usuario:clave@host:5432/base', hint: 'Requiere el driver psycopg2 (pip install psycopg2-binary).' },
    { id: 'mssql', label: 'SQL Server', tpl: 'mssql4://usuario:clave@host:1433/base?DRIVER={ODBC Driver 18 for SQL Server}', hint: 'Requiere pyodbc y un driver ODBC. DRIVER= elige cuál; agregá &TrustServerCertificate=yes si el servidor usa un certificado autofirmado.' },
    { id: 'mysql', label: 'MySQL / MariaDB', tpl: 'mysql://usuario:clave@host:3306/base', hint: 'Requiere el driver pymysql (pip install pymysql).' },
    { id: 'sqlite', label: 'SQLite', tpl: 'sqlite://C:/ruta/a/mi_base.db', hint: 'Un archivo local. Podés elegirlo con el botón de abajo.' },
    { id: 'other', label: 'Otro (pydal)', tpl: 'motor://usuario:clave@host:puerto/base', hint: 'Cualquier motor que pydal pueda abrir. Si no hay lector de esquema propio se intenta INFORMATION_SCHEMA estándar.' },
  ];
  const WIZARD_ENGINES = [['postgres', 'PostgreSQL'], ['mssql', 'SQL Server'], ['mysql', 'MySQL / MariaDB'], ['sqlite', 'SQLite']];

  Etch.dialogs.connection = async (opts) => {
    opts = opts || {};
    let existing = null;
    if (opts.alias) {
      const r = await Etch.api.get_connection(opts.alias);
      if (!r.ok) { Etch.toast('error', r.error); return; }
      existing = r;
    }
    const drivers = await Etch.api.list_drivers();
    const odbc = drivers.odbc || [];
    const engineInfo = drivers.engines || {};

    const input = (attrs) => h('input', Object.assign({ class: 'input', autocomplete: 'off', spellcheck: 'false' }, attrs));
    const alias = input({ maxlength: 60, placeholder: 'Ej: Producción, ETS, Home Server', value: existing ? existing.alias : '' });

    /* ---- asistente ---- */
    const typeSel = h('select', { class: 'select', 'aria-label': 'Tipo de base de datos' },
      WIZARD_ENGINES.map(([v, l]) => h('option', { value: v }, l)), h('option', { value: 'other' }, 'Otro motor… (URI avanzada)'));
    const host = input({ placeholder: 'Ej: 192.168.1.20 o db.miempresa.com', 'aria-label': 'Servidor' });
    const port = input({ inputmode: 'numeric', maxlength: 5, 'aria-label': 'Puerto' });
    const dbname = input({ placeholder: 'Nombre de la base', 'aria-label': 'Base de datos' });
    const user = input({ placeholder: 'Usuario', 'aria-label': 'Usuario' });
    const pass = input({ type: 'password', placeholder: 'Contraseña', 'aria-label': 'Contraseña', autocomplete: 'new-password' });
    const passEye = h('button', { type: 'button', class: 'btn icon-only ghost', 'aria-label': 'Mostrar u ocultar la contraseña' }, icon('eye', 16));
    passEye.addEventListener('click', () => {
      const hidden = pass.type === 'password';
      pass.type = hidden ? 'text' : 'password';
      passEye.replaceChildren(icon(hidden ? 'eyeoff' : 'eye', 16));
    });
    const driverIn = input({ list: 'odbc-drivers', placeholder: 'ODBC Driver 18 for SQL Server', 'aria-label': 'Driver ODBC' });
    const driverList = h('datalist', { id: 'odbc-drivers' }, odbc.map((d) => h('option', { value: d })));
    const trust = h('input', { type: 'checkbox', id: 'trust-cert' });
    const filePath = input({ placeholder: 'C:/ruta/a/mi_base.db', 'aria-label': 'Archivo SQLite' });
    const pickBtn = h('button', { type: 'button', class: 'btn sm', style: { marginTop: '8px' } }, icon('folder', 15), 'Elegir archivo…');
    pickBtn.addEventListener('click', async () => { const r = await Etch.api.pick_file(); if (r.ok) { filePath.value = r.path; refresh(); } });
    let extra = '', scheme = '';   // argumentos y variante de esquema que el asistente no edita pero conserva

    const wizHint = h('div', { class: 'hint', style: { minHeight: '18px' } });
    const netBlock = h('div', null,
      h('div', { class: 'row2' }, h('div', { class: 'field' }, h('label', null, 'Servidor (host o IP)'), host), h('div', { class: 'field' }, h('label', null, 'Puerto'), port)),
      h('div', { class: 'field' }, h('label', null, 'Base de datos'), dbname),
      h('div', { class: 'row2 even' }, h('div', { class: 'field' }, h('label', null, 'Usuario'), user),
        h('div', { class: 'field' }, h('label', null, 'Contraseña'), h('div', { class: 'input-group' }, pass, passEye))));
    const mssqlBlock = h('div', null,
      h('div', { class: 'field' }, h('label', null, 'Driver ODBC'), driverIn, driverList),
      h('label', { class: 'check', for: 'trust-cert' }, trust, h('span', null, 'Confiar en el certificado del servidor (necesario si usa uno autofirmado, común con el driver 18)')));
    const sqliteBlock = h('div', { class: 'field' }, h('label', null, 'Archivo de la base'), filePath, pickBtn);
    const preview = h('code', { class: 'truncate grow' });
    const copyBtn = h('button', { type: 'button', class: 'btn icon-only ghost', 'aria-label': 'Copiar la URI (con la contraseña)', title: 'Copiar la URI completa' }, icon('copy', 15));
    const previewBox = h('div', null,
      h('div', { class: 'field', style: { marginBottom: '6px' } }, h('div', { class: 'lab' }, 'URI resultante (la contraseña se oculta aquí)')),
      h('div', { class: 'uri-preview' }, preview, copyBtn));
    const wizard = h('div', null,
      h('div', { class: 'field' }, h('label', null, 'Tipo de base de datos'), typeSel), wizHint, netBlock, mssqlBlock, sqliteBlock, previewBox);

    /* ---- avanzado ---- */
    const uri = input({ class: 'input mono', placeholder: ADV_TEMPLATES[0].tpl });
    const eye = h('button', { type: 'button', class: 'btn icon-only ghost', 'aria-label': 'Mostrar u ocultar la URI' }, icon('eyeoff', 16));
    eye.addEventListener('click', () => {
      const hidden = uri.type === 'password';
      uri.type = hidden ? 'text' : 'password';
      eye.replaceChildren(icon(hidden ? 'eyeoff' : 'eye', 16));
    });
    const advHint = h('div', { class: 'hint', style: { minHeight: '34px' } });
    const advPick = h('button', { type: 'button', class: 'btn sm', style: { display: 'none', marginTop: '8px' } }, icon('folder', 15), 'Elegir archivo SQLite…');
    advPick.addEventListener('click', async () => { const r = await Etch.api.pick_file(); if (r.ok) { uri.value = 'sqlite://' + r.path.replace(/\\/g, '/'); checkAdv(); } });
    let advEngine = null;
    const chips = ADV_TEMPLATES.map((t) => h('button', { type: 'button', class: 'chip', 'aria-pressed': 'false', onclick: () => fillTemplate(t) }, t.label));
    function markAdv(id) {
      advEngine = id;
      chips.forEach((c, i) => c.setAttribute('aria-pressed', String(ADV_TEMPLATES[i].id === id)));
      advPick.style.display = id === 'sqlite' ? 'inline-flex' : 'none';
    }
    function fillTemplate(t) {
      if (!uri.value.trim() || ADV_TEMPLATES.some((x) => x.tpl === uri.value.trim())) uri.value = t.tpl;
      uri.type = 'text'; eye.replaceChildren(icon('eyeoff', 16));
      markAdv(t.id); checkAdv();
    }
    const checkAdv = debounce(async () => {
      const value = uri.value.trim();
      const tpl = ADV_TEMPLATES.find((t) => t.id === advEngine);
      if (!value) { advHint.className = 'hint'; advHint.textContent = tpl ? tpl.hint : 'Pegá tu URI de pydal, o elegí un motor para ver un ejemplo.'; return; }
      const r = await Etch.api.check_uri(value);
      if (r.engine) { const known = ADV_TEMPLATES.find((t) => t.id === r.engine); markAdv(known ? known.id : 'other'); }
      if (!r.engine) { advHint.className = 'hint warn'; advHint.textContent = 'No reconozco el motor del prefijo. Se intentará igual con pydal, pero revisá que la URI empiece con motor://'; }
      else if (r.driver_error) { advHint.className = 'hint warn'; advHint.textContent = r.driver_error; }
      else { advHint.className = 'hint good'; advHint.textContent = 'Motor detectado: ' + Etch.engineLabel(r.engine) + (r.reader === 'generic' ? ' (lectura de esquema genérica, puede no funcionar)' : '') + '. El driver está instalado.'; }
    }, 250);
    uri.addEventListener('input', () => { markAdv(advEngine); checkAdv(); });
    const advanced = h('div', null,
      h('div', { class: 'field' }, h('div', { class: 'lab' }, 'Rellenar un ejemplo'), h('div', { class: 'seg' }, chips)),
      h('div', { class: 'field' }, h('label', null, 'URI de conexión (pydal)'), h('div', { class: 'input-group' }, uri, eye), advPick),
      advHint);

    /* ---- modo ---- */
    let mode = 'wizard';
    const tabWizard = h('button', { type: 'button', class: 'tab', role: 'tab' }, icon('grid', 15), 'Asistente');
    const tabAdv = h('button', { type: 'button', class: 'tab', role: 'tab' }, icon('file', 15), 'URI avanzada');
    const testOut = h('div', { class: 'hint', style: { minHeight: '20px', marginTop: '4px' } });
    const err = h('div', { class: 'hint bad', style: { minHeight: '18px' } });

    function collect() {
      return { engine: typeSel.value, scheme, host: host.value, port: port.value, user: user.value, password: pass.value,
        database: dbname.value, driver: driverIn.value, trust_cert: trust.checked, path: filePath.value, extra };
    }
    function fill(f) {
      typeSel.value = f.engine; scheme = f.scheme || ''; extra = f.extra || '';
      host.value = f.host || ''; port.value = f.port || ''; user.value = f.user || ''; pass.value = f.password || '';
      dbname.value = f.database || ''; driverIn.value = f.driver || ''; trust.checked = !!f.trust_cert; filePath.value = f.path || '';
    }
    function layout() {
      const e = typeSel.value;
      netBlock.hidden = e === 'sqlite'; mssqlBlock.hidden = e !== 'mssql'; sqliteBlock.hidden = e !== 'sqlite';
      const info = engineInfo[e] || {};
      port.placeholder = info.port ? String(info.port) : '';
      if (e === 'mssql' && !driverIn.value && odbc.length) driverIn.value = odbc[0];
      if (info.driver_error) { wizHint.className = 'hint warn'; wizHint.textContent = info.driver_error; }
      else if (e === 'mssql' && !odbc.length) { wizHint.className = 'hint warn'; wizHint.textContent = 'No se detectó ningún driver ODBC de SQL Server. Instalá «ODBC Driver 18 for SQL Server» de Microsoft.'; }
      else { wizHint.className = 'hint'; wizHint.textContent = ''; }
    }
    let seq = 0;
    const refresh = debounce(async () => {
      const mine = ++seq;
      const r = await Etch.api.build_uri(collect());
      if (mine !== seq) return;
      preview.textContent = r.ok ? r.masked : r.error;
      preview.style.opacity = r.ok ? '1' : '.6';
      preview.dataset.ok = r.ok ? '1' : '';
    }, 120);
    [host, port, dbname, user, pass, driverIn, filePath].forEach((el) => el.addEventListener('input', refresh));
    trust.addEventListener('change', refresh);
    typeSel.addEventListener('change', () => {
      if (typeSel.value === 'other') { typeSel.value = 'postgres'; layout(); setMode('adv', 'other'); return; }
      scheme = ''; layout(); refresh();
    });
    copyBtn.addEventListener('click', async () => {
      const r = await Etch.api.build_uri(collect());
      if (r.ok && await Etch.copyText(r.uri)) Etch.toast('success', 'URI copiada', { timeout: 1800 });
    });

    async function setMode(next, template) {
      testOut.textContent = ''; err.textContent = '';
      if (next === 'adv') {
        if (mode === 'wizard') {
          const r = await Etch.api.build_uri(collect());
          if (r.ok) uri.value = r.uri;
        }
        mode = 'adv';
        if (template) { const t = ADV_TEMPLATES.find((x) => x.id === template); if (t) fillTemplate(t); }
        uri.type = uri.value ? 'password' : 'text'; eye.replaceChildren(icon(uri.type === 'password' ? 'eye' : 'eyeoff', 16));
        checkAdv();
      } else {
        const value = uri.value.trim();
        if (mode === 'adv' && value) {
          const r = await Etch.api.parse_uri(value);
          if (!r.ok) { advHint.className = 'hint warn'; advHint.textContent = 'El asistente no puede descomponer esta URI (motor no soportado o formato especial). Seguí con la URI avanzada.'; return; }
          fill(r.fields);
        }
        mode = 'wizard'; layout(); refresh();
      }
      wizard.hidden = mode !== 'wizard'; advanced.hidden = mode !== 'adv';
      tabWizard.setAttribute('aria-selected', String(mode === 'wizard')); tabAdv.setAttribute('aria-selected', String(mode === 'adv'));
    }
    tabWizard.addEventListener('click', () => { if (mode !== 'wizard') setMode('wizard'); });
    tabAdv.addEventListener('click', () => { if (mode !== 'adv') setMode('adv'); });

    async function currentUri() {
      if (mode === 'adv') return { ok: !!uri.value.trim(), uri: uri.value.trim(), error: 'Pegá o escribí la URI de conexión.' };
      return Etch.api.build_uri(collect());
    }
    async function runTest(btn) {
      testOut.className = 'hint'; testOut.textContent = 'Probando la conexión…';
      const u = await currentUri();
      if (!u.ok) { testOut.className = 'hint warn'; testOut.textContent = u.error; return; }
      btn.disabled = true;
      try {
        const r = await Etch.api.test_connection(u.uri);
        testOut.className = 'hint ' + (r.ok ? 'good' : 'bad');
        testOut.textContent = r.ok ? '✓ Conexión exitosa (' + r.seconds + ' s). Ya podés guardar y escanear.' : r.error;
      } finally { btn.disabled = false; }
    }
    async function submit(scan) {
      err.textContent = '';
      const u = await currentUri();
      if (!u.ok) { err.textContent = u.error; return false; }
      const r = await Etch.api.save_connection(alias.value, u.uri, existing ? existing.alias : null);
      if (!r.ok) { err.textContent = r.error; (r.error.includes('URI') ? (mode === 'adv' ? uri : host) : alias).focus(); return false; }
      await Etch.refreshConnections();
      if (!existing || Etch.state.alias === existing.alias) Etch.state.alias = r.alias;
      Etch.selectConnection(r.alias);
      if (scan) Etch.scan(r.alias);
      Etch.toast('success', existing ? 'Conexión actualizada' : 'Conexión guardada',
        { detail: scan ? 'Escaneando el esquema…' : 'Usá «Reescanear» cuando quieras leer el esquema.', timeout: 3000 });
      return true;
    }

    const m = modal({
      title: existing ? 'Editar conexión' : 'Nueva conexión', width: '640px',
      body: h('div', null,
        h('div', { class: 'field' }, h('label', null, 'Nombre'), alias),
        h('div', { class: 'tabs', role: 'tablist', style: { margin: '2px 0 14px', width: 'fit-content' } }, tabWizard, tabAdv),
        wizard, advanced, testOut,
        h('p', { class: 'hint', style: { margin: '6px 0 0' } },
          'La conexión se guarda en este equipo apenas tocás Guardar, aunque el escaneo falle: no vas a tener que volver a escribirla.'),
        err),
      buttons: [
        { label: 'Cancelar', kind: 'ghost' },
        { label: 'Probar conexión', icon: 'zap', onClick: () => { runTest(m.buttons[1]); return false; } },
        { label: 'Guardar', onClick: () => submit(false) },
        { label: 'Guardar y escanear', kind: 'primary', icon: 'play', onClick: () => submit(true) },
      ],
    });
    el_enter([alias, host, port, dbname, user, pass, driverIn, filePath, uri], () => m.buttons[3].click());
    function el_enter(els, fn) { els.forEach((el) => el.addEventListener('keydown', (e) => { if (e.key === 'Enter') fn(); })); }

    // estado inicial
    let start = null;
    if (existing) {
      const r = await Etch.api.parse_uri(existing.uri);
      if (r.ok) { fill(r.fields); start = 'wizard'; } else { uri.value = existing.uri; start = 'adv'; }
      if (existing.secret_error) { pass.value = ''; err.textContent = 'La contraseña guardada no se pudo descifrar (otro usuario o equipo de Windows). Escríbela de nuevo.'; }
    }
    if (!start) { typeSel.value = 'postgres'; start = 'wizard'; }
    if (start === 'adv') { mode = 'wizard'; uri.value = existing.uri; await setMode('adv'); }
    else { mode = 'adv'; await setMode('wizard'); }
    wizard.hidden = mode !== 'wizard'; advanced.hidden = mode !== 'adv';
    tabWizard.setAttribute('aria-selected', String(mode === 'wizard')); tabAdv.setAttribute('aria-selected', String(mode === 'adv'));
    alias.focus();
  };
})();
