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

  /* ---------------- conexión (crear / editar) ---------------- */
  const TEMPLATES = [
    { id: 'postgres', label: 'PostgreSQL', tpl: 'postgres://usuario:clave@host:5432/base', hint: 'Requiere el driver psycopg2 (pip install psycopg2-binary).' },
    { id: 'mssql', label: 'SQL Server', tpl: 'mssql4://usuario:clave@host:1433/base', hint: 'Requiere pyodbc y un driver ODBC. Para elegir driver agregá ?DRIVER={ODBC Driver 18 for SQL Server} (o {SQL Server}) al final.' },
    { id: 'mysql', label: 'MySQL / MariaDB', tpl: 'mysql://usuario:clave@host:3306/base', hint: 'Requiere el driver pymysql (pip install pymysql).' },
    { id: 'sqlite', label: 'SQLite', tpl: 'sqlite://C:/ruta/a/mi_base.db', hint: 'Un archivo local. Podés elegirlo con el botón de abajo.' },
    { id: 'other', label: 'Otro (pydal)', tpl: 'motor://usuario:clave@host:puerto/base', hint: 'Cualquier motor que pydal pueda abrir. Si no hay lector de esquema propio se intenta INFORMATION_SCHEMA estándar.' },
  ];

  Etch.dialogs.connection = async (opts) => {
    opts = opts || {};
    let existing = null;
    if (opts.alias) {
      const r = await Etch.api.get_connection(opts.alias);
      if (!r.ok) { Etch.toast('error', r.error); return; }
      existing = r;
    }
    const alias = h('input', { class: 'input', maxlength: 60, autocomplete: 'off', spellcheck: 'false',
      placeholder: 'Ej: Producción, ETS, Home Server', value: existing ? existing.alias : '' });
    const uri = h('input', { class: 'input mono', type: existing ? 'password' : 'text', autocomplete: 'off', spellcheck: 'false',
      placeholder: TEMPLATES[0].tpl, value: existing ? existing.uri : '' });
    const eye = h('button', { type: 'button', class: 'btn icon-only ghost', 'aria-label': 'Mostrar u ocultar la URI' }, icon(existing ? 'eye' : 'eyeoff', 16));
    eye.addEventListener('click', () => {
      const hidden = uri.type === 'password';
      uri.type = hidden ? 'text' : 'password';
      eye.replaceChildren(icon(hidden ? 'eyeoff' : 'eye', 16));
    });
    const hint = h('div', { class: 'hint', style: { minHeight: '34px' } });
    const err = h('div', { class: 'hint bad', style: { minHeight: '18px' } });
    const pickBtn = h('button', { type: 'button', class: 'btn sm', style: { display: 'none', marginTop: '8px' } }, icon('folder', 15), 'Elegir archivo SQLite…');
    pickBtn.addEventListener('click', async () => {
      const r = await Etch.api.pick_file();
      if (r.ok) { uri.value = 'sqlite://' + r.path.replace(/\\/g, '/'); check(); }
    });

    let currentEngine = null;
    const chips = TEMPLATES.map((t) => h('button', { type: 'button', class: 'chip', 'aria-pressed': 'false', onclick: () => pick(t) }, t.label));
    function pick(t) {
      const isTemplate = !uri.value.trim() || TEMPLATES.some((x) => x.tpl === uri.value.trim());
      if (isTemplate) uri.value = t.tpl;
      if (uri.type === 'password' && isTemplate) uri.type = 'text';
      mark(t.id); check();
    }
    function mark(id) {
      currentEngine = id;
      chips.forEach((c, i) => c.setAttribute('aria-pressed', String(TEMPLATES[i].id === id)));
      pickBtn.style.display = id === 'sqlite' ? 'inline-flex' : 'none';
    }
    const check = debounce(async () => {
      const value = uri.value.trim();
      const tpl = TEMPLATES.find((t) => t.id === currentEngine);
      if (!value) { hint.className = 'hint'; hint.textContent = tpl ? tpl.hint : 'Elegí un motor para ver un ejemplo, o pegá tu URI de pydal.'; return; }
      const r = await Etch.api.check_uri(value);
      if (r.engine) { const known = TEMPLATES.find((t) => t.id === r.engine); mark(known ? known.id : 'other'); }
      if (!r.engine) { hint.className = 'hint warn'; hint.textContent = 'No reconozco el motor del prefijo. Se intentará igual con pydal, pero revisá que la URI empiece con motor://'; }
      else if (r.driver_error) { hint.className = 'hint warn'; hint.textContent = r.driver_error; }
      else { hint.className = 'hint good'; hint.textContent = 'Motor detectado: ' + Etch.engineLabel(r.engine) + (r.reader === 'generic' ? ' (lectura de esquema genérica, puede no funcionar)' : '') + '. El driver está instalado.'; }
    }, 250);
    uri.addEventListener('input', check);

    async function submit(scan) {
      err.textContent = '';
      const r = await Etch.api.save_connection(alias.value, uri.value, existing ? existing.alias : null);
      if (!r.ok) { err.textContent = r.error; (r.error.includes('URI') ? uri : alias).focus(); return false; }
      await Etch.refreshConnections();
      if (!existing || Etch.state.alias === existing.alias) Etch.state.alias = r.alias;
      Etch.selectConnection(r.alias);
      if (scan) Etch.scan(r.alias);
      Etch.toast('success', existing ? 'Conexión actualizada' : 'Conexión guardada',
        { detail: scan ? 'Escaneando el esquema…' : 'Usá «Reescanear» cuando quieras leer el esquema.', timeout: 3000 });
      return true;
    }

    const m = modal({
      title: existing ? 'Editar conexión' : 'Nueva conexión', width: '600px',
      body: h('div', null,
        h('div', { class: 'field' }, h('label', null, 'Nombre'), alias),
        h('div', { class: 'field' }, h('div', { class: 'lab' }, 'Motor (rellena un ejemplo)'), h('div', { class: 'seg' }, chips)),
        h('div', { class: 'field' }, h('label', null, 'URI de conexión (pydal)'),
          h('div', { class: 'input-group' }, uri, eye), pickBtn),
        hint,
        h('p', { class: 'hint', style: { margin: '6px 0 0' } },
          'La conexión se guarda en este equipo apenas tocás Guardar, aunque el escaneo falle: no vas a tener que volver a escribirla.'),
        err),
      buttons: [
        { label: 'Cancelar', kind: 'ghost' },
        { label: 'Guardar', onClick: () => submit(false) },
        { label: 'Guardar y escanear', kind: 'primary', icon: 'play', onClick: () => submit(true) },
      ],
    });
    [alias, uri].forEach((el) => el.addEventListener('keydown', (e) => { if (e.key === 'Enter') m.buttons[2].click(); }));
    const startEngine = existing ? null : TEMPLATES[0].id;
    if (existing) check(); else { mark(startEngine); check(); }
    alias.focus();
  };
})();
