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
  const ui = { alias: null, target: null, opts: { name_style: '', target_schema: '', table_prefix: '', include_fks: true, include_uniques: true, include_identity: true, include_defaults: true, include_comments: true }, filter: 'all' };

  Etch.views.migrate = {
    render(root) {
      const S = Etch.state, sc = S.schema;
      if (ui.alias !== S.alias) { ui.alias = S.alias; ui.target = null; ui.filter = 'all'; }
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

      root.append(h('div', { class: 'page' },
        h('h1', null, 'Migrar a otro motor'),
        h('p', { class: 'lead' }, 'Genera el script para crear en otra base (PostgreSQL, SQL Server, MySQL o SQLite) las tablas de ', h('b', null, S.alias), ', con los tipos traducidos.'),
        h('div', { class: 'banner' }, icon('shield', 18), h('div', { class: 'grow' }, h('b', null, 'Fase 1: solo se genera un script. '),
          'La app no se conecta al destino ni escribe en ninguna base; tú revisas y ejecutas el SQL. Tu base de origen no se modifica. Copiar los datos llegará en una fase posterior, con más salvaguardas.')),
        h('div', { class: 'sec-title', style: { marginTop: '8px' } }, '1 · Motor de destino'), cards,
        h('div', { class: 'sec-title', style: { marginTop: '8px' } }, '2 · Opciones'), optBox,
        h('div', { class: 'row', style: { marginBottom: '8px' } }, goBtn,
          sc.meta && !sc.tables[Object.keys(sc.tables)[0]].columns.some((c) => c.prec || c.identity) ? h('span', { class: 'hint warn' }, 'Este escaneo no trae precisión ni identidades: reescanea para una traducción más fiel.') : null),
        out));
      paintCards(); paintOpts();
    },
  };
})();
