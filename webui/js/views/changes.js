/* Cambios: compara dos versiones del esquema de la misma conexión
   (cada escaneo que encuentra un esquema distinto guarda una versión nueva). */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon } = Etch;

  const label = (v) => Etch.fmtDate(v.at) + ' · ' + Etch.plural(v.tables, 'tabla', 'tablas');

  function stat(cls, num, text) {
    return h('div', { class: 'card stat' }, h('div', { class: 'num ' + cls }, Etch.num(num)), h('div', { class: 'lab' }, text));
  }

  function markdown(alias, res) {
    const d = res.diff, L = [];
    L.push('# Cambios en el esquema de ' + alias, '', 'Comparación: ' + Etch.fmtDate(res.older.at) + ' → ' + Etch.fmtDate(res.newer.at), '');
    if (d.added_tables.length) L.push('## Tablas nuevas', ...d.added_tables.map((t) => '- `' + t.name + '` (' + t.columns + ' columnas)'), '');
    if (d.removed_tables.length) L.push('## Tablas eliminadas', ...d.removed_tables.map((t) => '- `' + t.name + '`'), '');
    const names = Object.keys(d.changed_tables);
    if (names.length) {
      L.push('## Tablas modificadas');
      for (const n of names) {
        const c = d.changed_tables[n];
        L.push('', '### `' + n + '`');
        c.added_columns.forEach((x) => L.push('- + columna `' + x.name + '` ' + x.type));
        c.removed_columns.forEach((x) => L.push('- − columna `' + x.name + '`'));
        c.modified_columns.forEach((x) => L.push('- ~ columna `' + x.name + '`: ' + Object.entries(x.changes).map(([k, v]) => k + ' ' + v[0] + ' → ' + v[1]).join(', ')));
        c.added_relations.forEach((r) => L.push('- + relación `' + r[0] + '` → `' + r[1] + '.' + r[2] + '`'));
        c.removed_relations.forEach((r) => L.push('- − relación `' + r[0] + '` → `' + r[1] + '.' + r[2] + '`'));
      }
    }
    return L.join('\n');
  }

  function line(kind, ...parts) {
    return h('div', { class: 'diff-line ' + kind }, h('span', { class: 'sign' }, kind === 'add' ? '+' : kind === 'del' ? '−' : '~'), ...parts);
  }

  function renderDiff(box, alias, res) {
    const d = res.diff, s = d.summary;
    const link = (n) => h('button', { class: 'linkbtn', onclick: () => Etch.openTable(n) }, n);
    box.append(
      h('div', { class: 'change-grid' },
        stat('add', s.added_tables, 'Tablas nuevas'), stat('del', s.removed_tables, 'Tablas eliminadas'),
        stat('add', s.added_columns, 'Columnas nuevas'), stat('del', s.removed_columns, 'Columnas eliminadas'),
        stat('mod', s.modified_columns, 'Columnas modificadas'), stat('mod', s.added_relations + s.removed_relations, 'Cambios de relaciones')));

    if (!s.total) { box.append(h('div', { class: 'card empty' }, icon('check', 30), h('h2', null, 'Sin diferencias'), h('div', null, 'Estas dos versiones tienen el mismo esquema.'))); return; }

    if (d.added_tables.length) box.append(h('div', { class: 'sec-title' }, 'Tablas nuevas', h('span', { class: 'badge good' }, String(d.added_tables.length))),
      h('div', { class: 'diff-table' }, h('div', { class: 'body', style: { paddingTop: '10px' } }, d.added_tables.map((t) =>
        line('add', link(t.name), h('span', { class: 'ty' }, Etch.plural(t.columns, 'columna', 'columnas') + (t.relations ? ' · ' + Etch.plural(t.relations, 'relación', 'relaciones') : '')))))));
    if (d.removed_tables.length) box.append(h('div', { class: 'sec-title' }, 'Tablas eliminadas', h('span', { class: 'badge bad' }, String(d.removed_tables.length))),
      h('div', { class: 'diff-table' }, h('div', { class: 'body', style: { paddingTop: '10px' } }, d.removed_tables.map((t) =>
        line('del', h('span', { class: 'mono' }, t.name), h('span', { class: 'ty' }, Etch.plural(t.columns, 'columna', 'columnas')))))));

    const names = Object.keys(d.changed_tables);
    if (names.length) {
      box.append(h('div', { class: 'sec-title' }, 'Tablas modificadas', h('span', { class: 'badge warn' }, String(names.length))));
      names.forEach((n, i) => {
        const c = d.changed_tables[n];
        const count = c.added_columns.length + c.removed_columns.length + c.modified_columns.length + c.added_relations.length + c.removed_relations.length;
        box.append(h('details', { class: 'diff-table', open: names.length <= 6 || i < 3 },
          h('summary', null, icon('table', 15), h('span', { class: 'mono' }, n), h('span', { class: 'badge' }, Etch.plural(count, 'cambio', 'cambios'))),
          h('div', { class: 'body' },
            c.added_columns.map((x) => line('add', h('span', null, 'columna '), h('b', null, x.name), h('span', { class: 'ty' }, x.type))),
            c.removed_columns.map((x) => line('del', h('span', null, 'columna '), h('b', null, x.name), h('span', { class: 'ty' }, x.type))),
            c.modified_columns.map((x) => line('mod', h('span', null, 'columna '), h('b', null, x.name),
              h('span', { class: 'ty' }, Object.entries(x.changes).map(([k, v]) => (k === 'null' ? (v[1] ? 'ahora admite NULL' : 'ahora NOT NULL') : k === 'pk' ? (v[1] ? 'ahora es PK' : 'ya no es PK') : 'tipo ' + v[0] + ' → ' + v[1])).join(' · ')))),
            c.added_relations.map((r) => line('add', h('span', null, 'relación '), h('b', null, r[0]), h('span', { class: 'ty' }, '→ ' + r[1] + '.' + r[2]))),
            c.removed_relations.map((r) => line('del', h('span', null, 'relación '), h('b', null, r[0]), h('span', { class: 'ty' }, '→ ' + r[1] + '.' + r[2]))))));
      });
    }
  }

  Etch.views.changes = {
    render(root) {
      const S = Etch.state, alias = S.alias;
      const box = h('div', { class: 'page' }, h('div', { class: 'skeleton', style: { height: '120px' } }));
      root.append(box);

      (async () => {
        const vr = await Etch.api.list_versions(alias);
        if (!box.isConnected) return;
        box.replaceChildren();
        const versions = vr.ok ? vr.versions : [];
        box.append(h('h1', null, 'Cambios'),
          h('p', { class: 'lead' }, 'Qué cambió en el esquema de ', h('b', null, alias), ' entre dos escaneos. Cada vez que reescaneas y la base es distinta, se guarda una versión (se conservan las últimas 8).'));

        if (versions.length < 2) {
          box.append(h('div', { class: 'card empty' }, icon('refresh', 34), h('h2', null, 'Todavía no hay nada que comparar'),
            h('div', { style: { maxWidth: '52ch', margin: '0 auto' } }, versions.length
              ? 'Solo hay una versión guardada (' + label(versions[0]) + '). Reescanea más adelante: si la base cambió (tablas, columnas, claves o relaciones), aquí verás la diferencia.'
              : 'Escanea la conexión para empezar el historial.'),
            h('button', { class: 'btn', style: { marginTop: '14px' }, onclick: () => Etch.scan(alias) }, icon('refresh', 16), 'Reescanear ahora')));
          return;
        }

        let newer = 0, older = 1;
        const sel = (idx, from, to, onChange) => {
          const el = h('select', { class: 'select', 'aria-label': 'Versión' }, versions.slice(from, to).map((v) => h('option', { value: String(v.index) }, (v.index === 0 ? 'Actual · ' : '') + label(v))));
          el.value = String(idx);
          el.addEventListener('change', () => onChange(Number(el.value)));
          return el;
        };
        const pickers = h('div', { class: 'diff-pickers' });
        const result = h('div');
        let last = null;
        const copyBtn = h('button', { class: 'btn', onclick: async () => { if (last && await Etch.copyText(markdown(alias, last))) Etch.toast('success', 'Resumen copiado (Markdown)', { timeout: 1800 }); } }, icon('copy', 16), 'Copiar resumen');

        async function run() {
          pickers.replaceChildren(
            h('span', { class: 'muted' }, 'Desde'), sel(older, 1, versions.length, (v) => { older = v; if (newer >= older) newer = older - 1; run(); }),
            h('span', { class: 'muted' }, 'hasta'), sel(newer, 0, versions.length - 1, (v) => { newer = v; if (older <= newer) older = newer + 1; run(); }),
            h('div', { class: 'grow' }), copyBtn);
          result.replaceChildren(h('div', { class: 'skeleton', style: { height: '90px' } }));
          const res = await Etch.api.compare_versions(alias, newer, older);
          if (!result.isConnected) return;
          result.replaceChildren();
          if (!res.ok) { result.append(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, res.error))); return; }
          last = res;
          renderDiff(result, alias, res);
        }
        box.append(pickers, result);
        run();
      })();
    },
  };
})();
