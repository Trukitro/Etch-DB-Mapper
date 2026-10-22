/* Migrar (fase 1): genera el script SQL de creación de tablas para otro motor.
   Solo produce texto: no se conecta a ningún destino ni escribe en ninguna base. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon } = Etch;

  const TARGETS = [
    ['postgres', 'PostgreSQL', 'Tipos nativos, IDENTITY, esquemas.'],
    ['mssql', 'SQL Server', 'NVARCHAR, IDENTITY, esquemas, descripciones.'],
    ['mysql', 'MySQL / MariaDB', 'InnoDB, utf8mb4, AUTO_INCREMENT.'],
    ['sqlite', 'SQLite', 'Un archivo local; tipos simples.'],
  ];
  const ui = { mode: 'script', alias: null, target: null, opts: { name_style: '', target_schema: '', table_prefix: '', include_fks: true, include_uniques: true, include_identity: true, include_defaults: true, include_comments: true }, filter: 'all' };

  /* ============================ Fase 1: script de esquema ============================ */
  function scriptBody(S, sc) {
    {
      const out = h('div');
      const cards = h('div', { class: 'recent', style: { marginBottom: '16px' } });
      const optBox = h('details', { class: 'diff-table', style: { marginBottom: '14px' } });
      const goBtn = h('button', { class: 'btn primary', disabled: !ui.target, onclick: () => generate() }, icon('migrate', 16), 'Generar script');

      function paintCards() {
        cards.replaceChildren(...TARGETS.map(([id, label, hint]) => h('button', {
          class: 'card stat click', 'aria-pressed': String(ui.target === id), style: { textAlign: 'left', cursor: 'pointer', borderColor: ui.target === id ? 'var(--accent)' : null },
          onclick: () => { ui.target = id; paintCards(); paintOpts(); goBtn.disabled = false; },
        }, h('div', { class: 'row' }, h('b', { class: 'grow' }, label), id === sc.engine ? h('span', { class: 'badge' }, 'mismo motor') : null,
          ui.target === id ? h('span', { class: 'badge good' }, 'elegido') : null),
          h('div', { class: 'muted', style: { fontSize: '12.5px', marginTop: '6px' } }, hint))));
      }

      function paintOpts() {
        const t = ui.target, hasSchemas = t === 'postgres' || t === 'mssql';
        const text = (key, label, ph, disabled, hint) => h('div', { class: 'field', style: { margin: 0 } }, h('label', null, label),
          h('input', { class: 'input mono', value: ui.opts[key], placeholder: ph, disabled, maxlength: 60, autocomplete: 'off', spellcheck: 'false',
            oninput: (e) => { ui.opts[key] = e.target.value; } }), hint ? h('div', { class: 'hint' }, hint) : null);
        const check = (key, label, hint) => h('label', { class: 'check', style: { margin: '2px 0' } },
          h('input', { type: 'checkbox', checked: ui.opts[key], onchange: (e) => { ui.opts[key] = e.target.checked; } }),
          h('span', null, label, hint ? h('span', { class: 'faint' }, ' — ' + hint) : null));
        const styleSel = h('select', { class: 'select', 'aria-label': 'Estilo de nombres', onchange: (e) => { ui.opts.name_style = e.target.value; } },
          [['', 'Automático (minúsculas en PostgreSQL)'], ['keep', 'Conservar tal cual'], ['lower', 'Todo en minúsculas']].map(([v, l]) => h('option', { value: v, selected: ui.opts.name_style === v }, l)));
        optBox.replaceChildren(
          h('summary', null, icon('settings', 15), 'Opciones', h('span', { class: 'faint', style: { fontWeight: 400 } }, 'esquema nuevo, prefijo, qué incluir')),
          h('div', { class: 'body', style: { gap: '12px' } },
            h('div', { class: 'row2 even' },
              text('target_schema', 'Esquema nuevo en el destino', 'migrado', !hasSchemas, hasSchemas ? 'Aísla todo en un esquema que debe NO existir.' : 'Este motor no tiene esquemas: usa el prefijo.'),
              text('table_prefix', 'Prefijo de las tablas', 'mig_', false, 'Opcional. Evita choques con tablas existentes.')),
            h('div', { class: 'field', style: { margin: 0 } }, h('label', null, 'Nombres'), styleSel),
            h('div', null, check('include_fks', 'Claves foráneas'), check('include_uniques', 'Restricciones UNIQUE'), check('include_identity', 'Identidad / autoincremento'),
              check('include_defaults', 'Valores por defecto', 'solo los que se pueden traducir'), check('include_comments', 'Descripciones', 'las de la base y tus notas'))));
      }

      async function generate() {
        if (!ui.target) return;
        goBtn.disabled = true;
        out.replaceChildren(h('div', { class: 'skeleton', style: { height: '140px' } }));
        const o = Object.assign({}, ui.opts);
        if (!o.name_style) delete o.name_style;
        const r = await Etch.api.plan_migration(S.alias, ui.target, o);
        goBtn.disabled = false;
        out.replaceChildren();
        if (!r.ok) { out.append(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, r.error))); return; }
        renderResult(r);
      }

      function renderResult(r) {
        const st = r.stats;
        const chip = (n, label, cls) => h('span', { class: 'badge ' + (cls || '') }, Etch.num(n) + ' ' + label);
        out.append(
          h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '8px', margin: '4px 0 12px' } },
            chip(st.tables, 'tablas'), chip(st.columns, 'columnas'), chip(st.foreign_keys, 'claves foráneas'), chip(st.uniques, 'UNIQUE'), chip(st.identities, 'identidades'),
            chip(st.warnings, st.warnings === 1 ? 'aviso' : 'avisos', st.warnings ? 'warn' : 'good'), chip(st.errors, st.errors === 1 ? 'error' : 'errores', st.errors ? 'bad' : 'good')));
        if (st.errors) out.append(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, h('b', null, 'Hay ' + st.errors + (st.errors === 1 ? ' error' : ' errores') + '. '),
          'El script no es fiable hasta corregirlos (por ejemplo con un prefijo o un esquema distinto). Míralos abajo.')));

        // advertencias
        const levels = [['all', 'Todo'], ['error', 'Errores'], ['warn', 'Avisos'], ['info', 'Información']];
        const warnBox = h('div', { class: 'rel' });
        const chips = h('div', { class: 'chips', style: { margin: '6px 0 10px' } });
        const paintWarn = () => {
          chips.replaceChildren(...levels.map(([id, l]) => h('button', { class: 'chip', 'aria-pressed': String(ui.filter === id), onclick: () => { ui.filter = id; paintWarn(); } }, l)));
          const list = r.warnings.filter((w) => ui.filter === 'all' || w.level === ui.filter).sort((a, b) => ['error', 'warn', 'info'].indexOf(a.level) - ['error', 'warn', 'info'].indexOf(b.level));
          warnBox.replaceChildren(...(list.length ? list.map((w) => h('div', { class: 'r' },
            h('span', { class: 'badge ' + (w.level === 'error' ? 'bad' : w.level === 'warn' ? 'warn' : '') }, w.level === 'error' ? 'error' : w.level === 'warn' ? 'aviso' : 'info'),
            w.table ? h('span', { class: 'mono' }, w.table + (w.column ? '.' + w.column : '')) : null, h('span', { class: 'muted' }, w.message))) : [h('div', { class: 'muted' }, 'Nada que mostrar.')]));
        };
        paintWarn();
        out.append(h('div', { class: 'sec-title' }, 'Advertencias', h('span', { class: 'badge' }, String(r.warnings.length))), chips, warnBox);

        // mapa de tipos
        out.append(h('div', { class: 'sec-title' }, 'Cómo se traduce cada columna'));
        r.tables.forEach((t, i) => out.append(h('details', { class: 'diff-table', open: false },
          h('summary', null, icon('table', 15), h('span', { class: 'mono' }, t.name), h('span', { class: 'faint', style: { fontWeight: 400 } }, '→ ' + t.target_name), h('span', { class: 'badge' }, Etch.plural(t.columns.length, 'columna', 'columnas'))),
          h('div', { class: 'body' }, h('table', { class: 'cols' },
            h('thead', null, h('tr', null, ['Columna', 'Tipo de origen', 'Tipo en el destino', ''].map((x) => h('th', null, x)))),
            h('tbody', null, t.columns.map((c) => h('tr', null, h('td', { class: 'nm' }, c.name, c.name !== c.target_name ? h('span', { class: 'faint' }, ' → ' + c.target_name) : null),
              h('td', { class: 'ty' }, c.source_type), h('td', { class: 'ty', style: { color: 'var(--text)' } }, c.target_type),
              h('td', null, c.pk ? h('span', { class: 'badge pk' }, 'PK') : null, ' ', c.identity ? h('span', { class: 'badge' }, 'identidad') : null)))))))));

        // script
        const copyBtn = h('button', { class: 'btn', onclick: async () => { if (await Etch.copyText(r.sql)) Etch.toast('success', 'Script copiado', { timeout: 1800 }); } }, icon('copy', 16), 'Copiar');
        const saveBtn = h('button', { class: 'btn primary', onclick: async () => {
          const s = await Etch.api.save_file(r.filename, r.file_content);
          if (s.ok) Etch.toast('success', 'Script guardado', { detail: s.path });
          else if (!s.cancelled) Etch.toast('error', 'No se pudo guardar', { detail: s.error });
        } }, icon('download', 16), 'Guardar .sql');
        out.append(h('div', { class: 'sec-title' }, 'Script'),
          h('div', { class: 'row', style: { gap: '8px', marginBottom: '8px' } }, saveBtn, copyBtn,
            h('span', { class: 'faint', style: { fontSize: '12.5px' } }, 'Ejecútalo tú, en una base NUEVA o vacía del destino. Solo crea objetos: sin DROP, TRUNCATE, DELETE ni UPDATE.')),
          h('pre', { class: 'sql', style: { maxHeight: '520px' } }, r.sql));
      }

      const el = h('div', null,
        h('div', { class: 'banner' }, icon('shield', 18), h('div', { class: 'grow' }, h('b', null, 'Solo se genera un script. '),
          'La app no se conecta al destino ni escribe en ninguna base; tú revisas y ejecutas el SQL. Tu base de origen no se modifica. Si prefieres que la app copie también los datos, usa «Copiar datos».')),
        h('div', { class: 'sec-title', style: { marginTop: '8px' } }, '1 · Motor de destino'), cards,
        h('div', { class: 'sec-title', style: { marginTop: '8px' } }, '2 · Opciones'), optBox,
        h('div', { class: 'row', style: { marginBottom: '8px' } }, goBtn,
          sc.meta && !sc.tables[Object.keys(sc.tables)[0]].columns.some((c) => c.prec || c.identity) ? h('span', { class: 'hint warn' }, 'Este escaneo no trae precisión ni identidades: reescanea para una traducción más fiel.') : null),
        out);
      paintCards(); paintOpts();
      return el;
    }
  }

  /* ============================ Fase 2: copiar datos ============================ */
  const cp = { target: '', plan: null, running: false, progress: null, report: null, dry: false, startedAt: 0 };
  let live = null;     // refrescadores de la vista montada

  Etch.on('copy_started', (e) => { cp.running = true; cp.dry = !!e.dry_run; cp.report = null; cp.progress = { tables_total: e.tables_total, rows_all: e.rows_all, rows_copied_total: 0, index: 0, rows_done: 0, rows_total: 0, table: '' }; cp.startedAt = Date.now(); if (live) live.all(); });
  Etch.on('copy_progress', (p) => { cp.progress = p; if (live) live.progress(); });
  Etch.on('copy_finished', (r) => {
    cp.running = false; cp.report = r;
    if (!r.dry_run) cp.plan = null;                  // tras una copia real hay que revisar de nuevo (el destino ya no está vacío)
    Etch.toast(r.ok ? 'success' : (r.cancelled ? 'warning' : 'error'), r.ok ? (r.dry_run ? 'Simulacro correcto' : 'Copia terminada') : (r.cancelled ? 'Copia cancelada' : 'La copia se detuvo'),
      { detail: r.ok ? Etch.plural(r.rows_copied, 'fila', 'filas') + ' en ' + Etch.fmtDuration(r.seconds) : (r.errors[0] || ''), timeout: 9000 });
    if (live) live.all();
  });

  const optionsEl = (engine) => {
    const hasSchemas = engine === 'postgres' || engine === 'mssql';
    const text = (key, label, ph, disabled, hint) => h('div', { class: 'field', style: { margin: 0 } }, h('label', null, label),
      h('input', { class: 'input mono', value: ui.opts[key], placeholder: ph, disabled, maxlength: 60, autocomplete: 'off', spellcheck: 'false', oninput: (e) => { ui.opts[key] = e.target.value; } }),
      hint ? h('div', { class: 'hint' }, hint) : null);
    return h('details', { class: 'diff-table', style: { marginBottom: '14px' } },
      h('summary', null, icon('settings', 15), 'Opciones', h('span', { class: 'faint', style: { fontWeight: 400 } }, 'esquema nuevo o prefijo para no mezclar con lo que ya haya en el destino')),
      h('div', { class: 'body', style: { gap: '12px' } },
        h('div', { class: 'row2 even' },
          text('target_schema', 'Esquema nuevo en el destino', 'migrado', !hasSchemas, hasSchemas ? 'Debe NO existir: lo crea la copia.' : 'Este motor no tiene esquemas: usa el prefijo.'),
          text('table_prefix', 'Prefijo de las tablas', 'mig_', false, 'Opcional. Permite copiar a un destino que ya tiene otras tablas (sin colisiones).'))));
  };
  const cleanOpts = () => { const o = Object.assign({}, ui.opts); if (!o.name_style) delete o.name_style; return o; };

  function copyBody(S) {
    const planBox = h('div'), progBox = h('div'), repBox = h('div'), optHolder = h('div');
    const others = S.connections.filter((c) => c.alias !== S.alias);
    const sel = h('select', { class: 'select', 'aria-label': 'Conexión de destino', disabled: cp.running },
      h('option', { value: '' }, others.length ? 'Elige la base de destino…' : 'Aún no hay otra conexión: crea la del destino'),
      others.map((c) => h('option', { value: c.alias, selected: cp.target === c.alias }, c.alias + '  ·  ' + Etch.engineLabel(c.engine))));
    sel.addEventListener('change', () => { cp.target = sel.value; cp.plan = null; paintOpts(); paintPlan(); reviewBtn.disabled = !cp.target; });
    const reviewBtn = h('button', { class: 'btn primary', disabled: !cp.target || cp.running, onclick: () => review() }, icon('search', 16), 'Revisar (no escribe nada)');
    const engineOf = () => (S.connections.find((c) => c.alias === cp.target) || {}).engine;
    const paintOpts = () => { optHolder.replaceChildren(optionsEl(engineOf())); };

    async function review() {
      reviewBtn.disabled = true; cp.plan = null; cp.report = null; paintRep();
      planBox.replaceChildren(h('div', { class: 'skeleton', style: { height: '140px' } }));
      const r = await Etch.api.preflight_copy(S.alias, cp.target, cleanOpts());
      reviewBtn.disabled = !cp.target || cp.running;
      if (!r.ok) { planBox.replaceChildren(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, r.error))); return; }
      cp.plan = r; paintPlan();
    }

    function paintPlan() {
      const r = cp.plan;
      if (!r) { planBox.replaceChildren(); return; }
      const st = r.stats, chip = (n, l, c) => h('span', { class: 'badge ' + (c || '') }, Etch.num(n) + ' ' + l);
      const parts = [
        h('div', { class: 'sec-title' }, '3 · Revisión del plan'),
        h('div', { class: 'banner' }, icon('shield', 18), h('div', { class: 'grow' }, h('b', null, 'Origen en solo lectura. '), r.read_only.note)),
      ];
      if (r.blockers.length) parts.push(h('div', { class: 'banner bad', style: { display: 'block' } }, h('div', { class: 'row', style: { marginBottom: '4px' } }, icon('alert', 18), h('b', null, 'No se puede copiar todavía:')),
        h('ul', { style: { margin: '4px 0 0', paddingLeft: '22px' } }, r.blockers.map((b) => h('li', null, b)))));
      else parts.push(h('div', { class: 'banner', style: { borderColor: 'color-mix(in srgb, var(--good) 45%, transparent)' } }, icon('check', 18), h('div', { class: 'grow' }, h('b', null, 'El destino cumple las condiciones. '), 'Está vacío (o sin colisiones con tus nombres) y se puede crear todo desde cero.')));
      parts.push(h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '8px', margin: '8px 0 12px' } },
        chip(st.tables, 'tablas'), chip(r.total_rows, 'filas a copiar'), chip(st.foreign_keys, 'claves foráneas'),
        chip(st.warnings, st.warnings === 1 ? 'aviso' : 'avisos', st.warnings ? 'warn' : 'good'), chip(st.errors, st.errors === 1 ? 'error' : 'errores', st.errors ? 'bad' : 'good')));
      parts.push(h('details', { class: 'diff-table' }, h('summary', null, icon('table', 15), 'Tablas y filas', h('span', { class: 'badge' }, String(r.tables.length))),
        h('div', { class: 'body' }, h('table', { class: 'cols' }, h('thead', null, h('tr', null, ['Tabla de origen', 'Se creará como', 'Filas'].map((x) => h('th', null, x)))),
          h('tbody', null, r.tables.map((t) => h('tr', null, h('td', { class: 'nm' }, t.name), h('td', { class: 'ty' }, t.target_name), h('td', { class: 'ty' }, Etch.num(t.rows)))))))));
      const warns = r.warnings.filter((w) => w.level !== 'info');
      if (warns.length) parts.push(h('details', { class: 'diff-table' }, h('summary', null, icon('alert', 15), 'Advertencias de la traducción', h('span', { class: 'badge warn' }, String(warns.length))),
        h('div', { class: 'body' }, warns.slice(0, 60).map((w) => h('div', { class: 'diff-line' }, h('span', { class: 'sign' }, '!'), w.table ? h('span', null, w.table + (w.column ? '.' + w.column : '') + ':') : null, h('span', { class: 'ty' }, w.message))))));
      if (r.existing.length) parts.push(h('div', { class: 'hint', style: { margin: '6px 0' } }, 'Tablas que ya tiene el destino (no se tocan): ' + r.existing.slice(0, 8).join(', ') + (r.existing.length > 8 ? ' …' : '')));
      parts.push(h('div', { class: 'row', style: { gap: '10px', flexWrap: 'wrap', margin: '14px 0 4px' } },
        h('button', { class: 'btn', disabled: !r.can_start || cp.running, onclick: () => start(true) }, icon('play', 16), 'Simulacro (leer y validar, sin escribir)'),
        h('button', { class: 'btn primary', disabled: !r.can_start || cp.running, onclick: () => confirmCopy(r) }, icon('database', 16), 'Copiar datos…'),
        h('span', { class: 'faint', style: { fontSize: '12.5px' } }, 'El simulacro lee todo el origen y comprueba las conversiones; no escribe nada.')));
      planBox.replaceChildren(...parts);
    }

    async function start(dry, confirmText) {
      const r = await Etch.api.start_copy(cp.plan.token, confirmText || '', dry);
      if (!r.ok) Etch.toast('error', 'No se pudo iniciar', { detail: r.error, timeout: 10000 });
      return r.ok;
    }

    function confirmCopy(r) {
      const input = h('input', { class: 'input mono', placeholder: cp.target, autocomplete: 'off', spellcheck: 'false', 'data-autofocus': '', 'aria-label': 'Nombre del destino' });
      const m = Etch.modal({
        title: 'Copiar los datos', width: '560px',
        body: h('div', null,
          h('p', { style: { margin: '4px 0 10px' } }, 'Se van a crear ', h('b', null, Etch.plural(r.stats.tables, 'tabla', 'tablas')), ' y copiar ', h('b', null, Etch.plural(r.total_rows, 'fila', 'filas')), ' en ', h('b', null, cp.target), ' (' + Etch.engineLabel(r.target_engine) + ').'),
          h('ul', { class: 'muted', style: { margin: '0 0 12px', paddingLeft: '20px', fontSize: '13px' } },
            h('li', null, 'El origen solo se lee: no se modifica.'), h('li', null, 'En el destino solo se CREA: nada se borra ni se sobrescribe.'),
            h('li', null, 'Si algo falla, se detiene y se informa; las tablas ya terminadas quedan.')),
          h('div', { class: 'field' }, h('label', null, 'Para confirmar, escribe el nombre del destino: ', h('b', { class: 'mono' }, cp.target)), input)),
        buttons: [{ label: 'Cancelar', kind: 'ghost' }, { label: 'Copiar ahora', kind: 'primary', icon: 'play', onClick: async () => { const ok = await start(false, input.value); return ok ? true : false; } }],
      });
      const go = m.buttons[1];
      go.disabled = true;
      input.addEventListener('input', () => { go.disabled = input.value.trim() !== cp.target; });
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !go.disabled) go.click(); });
    }

    function paintProgress() {
      if (!cp.running) { progBox.replaceChildren(); return; }
      const p = cp.progress || {};
      const pct = p.rows_all ? Math.min(100, Math.round((p.rows_copied_total || 0) / p.rows_all * 100)) : (p.tables_total ? Math.round(((p.index || 0) / p.tables_total) * 100) : 0);
      const secs = (Date.now() - cp.startedAt) / 1000;
      progBox.replaceChildren(h('div', { class: 'card', style: { margin: '14px 0' } },
        h('div', { class: 'row', style: { justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' } },
          h('b', null, cp.dry ? 'Simulacro en curso…' : 'Copiando…'),
          h('button', { class: 'btn sm danger', onclick: async () => { const r = await Etch.api.cancel_copy(); if (r.ok) Etch.toast('info', 'Cancelando…', { detail: 'Termina el lote en curso y revierte la tabla actual.', timeout: 3000 }); } }, icon('x', 14), 'Cancelar')),
        h('div', { class: 'meter' }, h('span', { style: { width: Math.max(pct, 2) + '%' } })),
        h('div', { class: 'muted', style: { fontSize: '13px' } },
          p.table ? ['Tabla ', h('b', { class: 'mono' }, p.table), ' · ' + Etch.num(p.rows_done) + ' de ' + Etch.num(p.rows_total) + ' filas · tabla ' + ((p.index || 0) + 1) + ' de ' + (p.tables_total || '?')] : 'Preparando…',
          h('span', { class: 'faint' }, ' · ' + pct + ' % · ' + Etch.fmtDuration(secs)))));
    }

    function paintRep() {
      const r = cp.report;
      if (!r) { repBox.replaceChildren(); return; }
      const kind = r.ok ? 'good' : (r.cancelled ? 'warn' : 'bad');
      const title = r.ok ? (r.dry_run ? 'Simulacro correcto: se pudo leer y convertir todo' : 'Copia terminada y verificada') : (r.cancelled ? 'Copia cancelada' : 'La copia se detuvo');
      const lines = [];
      r.errors.forEach((e) => lines.push('ERROR: ' + e));
      r.warnings.forEach((w) => lines.push('AVISO: ' + w));
      const text = [title, Etch.plural(r.rows_copied, 'fila', 'filas') + ' en ' + Etch.fmtDuration(r.seconds), ''].concat(r.tables.map((t) => (t.ok ? 'OK    ' : 'FALLÓ ') + t.name + ' -> ' + t.target_name + '  filas copiadas: ' + t.rows_copied + (t.rows_target != null ? '  en destino: ' + t.rows_target : ''))).concat([''], lines).join(String.fromCharCode(10));
      repBox.replaceChildren(h('div', { class: 'sec-title' }, 'Resultado'),
        h('div', { class: 'banner ' + (kind === 'bad' ? 'bad' : ''), style: kind === 'good' ? { borderColor: 'color-mix(in srgb, var(--good) 45%, transparent)' } : null }, icon(r.ok ? 'check' : 'alert', 18),
          h('div', { class: 'grow' }, h('b', null, title + '. '), Etch.plural(r.rows_copied, 'fila', 'filas') + ' en ' + Etch.fmtDuration(r.seconds) + '.')),
        r.errors.length ? h('div', { class: 'banner bad', style: { display: 'block' } }, r.errors.map((e) => h('div', { class: 'mono', style: { fontSize: '12.5px', whiteSpace: 'pre-wrap' } }, e))) : null,
        r.warnings.length ? h('div', { class: 'rel', style: { margin: '8px 0' } }, r.warnings.map((w) => h('div', { class: 'r' }, h('span', { class: 'badge warn' }, 'aviso'), h('span', { class: 'muted' }, w)))) : null,
        h('details', { class: 'diff-table', open: true }, h('summary', null, icon('table', 15), 'Tablas', h('span', { class: 'badge' }, String(r.tables.length))),
          h('div', { class: 'body' }, h('table', { class: 'cols' }, h('thead', null, h('tr', null, ['Tabla', 'Se creó como', 'Copiadas', 'En destino', ''].map((x) => h('th', null, x)))),
            h('tbody', null, r.tables.map((t) => h('tr', null, h('td', { class: 'nm' }, t.name), h('td', { class: 'ty' }, t.target_name), h('td', { class: 'ty' }, Etch.num(t.rows_copied)),
              h('td', { class: 'ty' }, t.rows_target == null ? '—' : Etch.num(t.rows_target)), h('td', null, h('span', { class: 'badge ' + (t.ok ? 'good' : 'bad') }, t.ok ? 'ok' : 'falló')))))))),
        h('div', { class: 'row', style: { margin: '8px 0' } }, h('button', { class: 'btn sm', onclick: async () => { if (await Etch.copyText(text)) Etch.toast('success', 'Informe copiado', { timeout: 1800 }); } }, icon('copy', 14), 'Copiar informe')));
    }

    live = { all: () => { paintPlan(); paintProgress(); paintRep(); sel.disabled = cp.running; reviewBtn.disabled = !cp.target || cp.running; }, progress: paintProgress };
    const el = h('div', null,
      h('div', { class: 'banner', style: { borderColor: 'color-mix(in srgb, var(--warn) 50%, transparent)', background: 'color-mix(in srgb, var(--warn) 8%, var(--panel))' } }, icon('alert', 18),
        h('div', { class: 'grow' }, h('b', null, 'Esta función escribe en la base de destino. '),
          'El origen solo se lee (la propia base lo impone en PostgreSQL, MySQL y SQLite; en SQL Server la app solo emite SELECT: usa un login de solo lectura). El destino debe ser una base ',
          h('b', null, 'nueva o vacía'), ': nada se borra ni se sobrescribe, y si hay cualquier conflicto la app se niega. Antes de escribir hay un plan y un simulacro que no tocan nada.')),
      h('div', { class: 'sec-title', style: { marginTop: '8px' } }, '1 · Base de destino'),
      h('div', { class: 'row', style: { gap: '10px', flexWrap: 'wrap', marginBottom: '14px' } }, h('div', { style: { minWidth: '320px', flex: '1 1 320px' } }, sel),
        h('button', { class: 'btn', disabled: cp.running, onclick: () => Etch.dialogs.connection() }, icon('plus', 16), 'Nueva conexión'),
        h('span', { class: 'faint', style: { fontSize: '12.5px' } }, 'Crea primero la conexión de la base de destino (vacía). Su motor define el tipo de script.')),
      h('div', { class: 'sec-title', style: { marginTop: '8px' } }, '2 · Opciones'), optHolder,
      h('div', { class: 'row', style: { marginBottom: '8px' } }, reviewBtn), planBox, progBox, repBox);
    paintOpts(); paintPlan(); paintProgress(); paintRep();
    return el;
  }

  /* ============================ Vista ============================ */
  Etch.views.migrate = {
    render(root) {
      const S = Etch.state, sc = S.schema;
      if (ui.alias !== S.alias) { ui.alias = S.alias; ui.target = null; ui.filter = 'all'; cp.target = ''; cp.plan = null; cp.report = null; ui.mode = 'script'; }
      const body = h('div');
      const tab = (id, label, ico) => h('button', { class: 'tab', role: 'tab', 'aria-selected': String(ui.mode === id), onclick: () => { ui.mode = id; paint(); } }, icon(ico, 15), label);
      const tabs = h('div', { class: 'tabs', role: 'tablist', style: { width: 'fit-content', margin: '4px 0 16px' } });
      function paint() {
        live = null;
        tabs.replaceChildren(tab('script', 'Script de esquema', 'file'), tab('copy', 'Copiar datos', 'database'));
        body.replaceChildren(ui.mode === 'copy' ? copyBody(S) : scriptBody(S, sc));
      }
      root.append(h('div', { class: 'page' },
        h('h1', null, 'Migrar a otro motor'),
        h('p', { class: 'lead' }, 'Lleva las tablas de ', h('b', null, S.alias), ' a PostgreSQL, SQL Server, MySQL o SQLite: primero genera el script de esquema (solo texto) y, si quieres, copia también los datos con salvaguardas.'),
        tabs, body));
      paint();
    },
    destroy() { live = null; },
  };
})();
