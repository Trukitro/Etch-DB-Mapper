/* Explorador: lista buscable de tablas + detalle (columnas, relaciones, DDL). */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon, $, clear, debounce } = Etch;

  const FILTERS = [['all', 'Todas'], ['related', 'Con relaciones'], ['orphans', 'Huérfanas'], ['nopk', 'Sin PK']];
  const SORTS = [['name', 'Nombre'], ['columns', 'Más columnas'], ['relations', 'Más relaciones']];
  const MAX_ROWS = 400;

  const ui = { q: '', filter: 'all', sort: 'name', selected: null, alias: null, limit: MAX_ROWS };

  function degree(t) { return t.relations.length + t.referenced_by.length; }

  function matches(name, t, q) {
    if (!q) return { ok: true };
    const ql = q.toLowerCase();
    if (name.toLowerCase().includes(ql)) return { ok: true };
    const col = t.columns.find((c) => c.name.toLowerCase().includes(ql));
    return col ? { ok: true, col: col.name } : { ok: false };
  }

  function compute() {
    const tables = Etch.state.schema.tables;
    const rows = [];
    for (const [name, t] of Object.entries(tables)) {
      const m = matches(name, t, ui.q);
      if (!m.ok) continue;
      const deg = degree(t);
      if (ui.filter === 'related' && !deg) continue;
      if (ui.filter === 'orphans' && deg) continue;
      if (ui.filter === 'nopk' && t.columns.some((c) => c.pk)) continue;
      rows.push({ name, t, deg, hit: m.col });
    }
    const by = {
      name: (a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
      columns: (a, b) => b.t.columns.length - a.t.columns.length || a.name.localeCompare(b.name),
      relations: (a, b) => b.deg - a.deg || a.name.localeCompare(b.name),
    };
    rows.sort(by[ui.sort] || by.name);
    return rows;
  }

  Etch.views.explorer = {
    render(root, args) {
      const S = Etch.state, tables = S.schema.tables, names = Object.keys(tables);
      if (ui.alias !== S.alias) Object.assign(ui, { q: '', filter: 'all', sort: 'name', selected: null, alias: S.alias, limit: MAX_ROWS });
      if (args.filter) ui.filter = args.filter;
      if (args.sort) ui.sort = args.sort;
      if (args.table && tables[args.table]) { ui.selected = args.table; ui.q = ''; ui.filter = 'all'; }
      if (ui.selected && !tables[ui.selected]) ui.selected = null;

      const search = h('input', { id: 'search-box', class: 'input', type: 'search', autocomplete: 'off', spellcheck: 'false',
        placeholder: 'Buscar tabla o columna…', value: ui.q, 'aria-label': 'Buscar tabla o columna' });
      const chipsEl = h('div', { class: 'chips', role: 'group', 'aria-label': 'Filtros' });
      const sortSel = h('select', { class: 'select', style: { height: '28px', width: 'auto', fontSize: '12px', padding: '0 8px' }, 'aria-label': 'Ordenar' },
        SORTS.map(([v, l]) => h('option', { value: v, selected: v === ui.sort }, l)));
      const count = h('span');
      const items = h('div', { class: 'ex-items', role: 'listbox', 'aria-label': 'Tablas' });
      const detail = h('div', { class: 'ex-detail' });

      let rows = [];
      function paintChips() {
        clear(chipsEl).append(...FILTERS.map(([id, label]) => h('button', { class: 'chip', 'aria-pressed': String(ui.filter === id),
          onclick: () => { ui.filter = id; ui.limit = MAX_ROWS; refresh(); } }, label)));
      }
      function paintList() {
        clear(items);
        count.textContent = rows.length === names.length ? Etch.plural(names.length, 'tabla', 'tablas') : rows.length + ' de ' + Etch.plural(names.length, 'tabla', 'tablas');
        if (!rows.length) {
          items.append(h('div', { class: 'empty' }, icon('search', 30), h('h2', null, 'Sin resultados'),
            h('div', null, 'Probá con otra palabra o quitá el filtro.'),
            h('button', { class: 'btn sm', style: { marginTop: '12px' }, onclick: () => { ui.q = ''; ui.filter = 'all'; search.value = ''; refresh(); } }, 'Limpiar búsqueda')));
          return;
        }
        const frag = document.createDocumentFragment();
        rows.slice(0, ui.limit).forEach((r) => {
          frag.append(h('button', { class: 'item' + (r.deg ? ' rel' : ''), role: 'option', 'data-name': r.name, 'aria-selected': String(r.name === ui.selected),
            onclick: () => select(r.name) },
            h('div', { class: 't' }, icon('table', 15), h('span', { class: 'truncate' }, Etch.highlight(r.name, ui.q))),
            h('div', { class: 'm' }, h('span', null, r.t.columns.length + ' col.'),
              r.deg ? h('span', { style: { color: 'var(--accent)' } }, icon('link', 12), ' ' + r.deg) : null,
              r.hit ? h('span', { class: 'truncate', style: { color: 'var(--accent)' } }, 'col: ', Etch.highlight(r.hit, ui.q)) : null)));
        });
        if (rows.length > ui.limit) {
          frag.append(h('button', { class: 'btn sm block', style: { margin: '8px 0' }, onclick: () => { ui.limit += MAX_ROWS; paintList(); } },
            'Mostrar más (' + (rows.length - ui.limit) + ' restantes)'));
        }
        items.append(frag);
      }
      function refresh() {
        rows = compute();
        paintChips(); paintList();
        if (!rows.some((r) => r.name === ui.selected)) ui.selected = rows.length ? rows[0].name : null;
        paintDetail();
        markSelected(true);
      }
      function markSelected(scroll) {
        items.querySelectorAll('.item').forEach((el) => {
          const on = el.dataset.name === ui.selected;
          el.setAttribute('aria-selected', String(on));
          if (on && scroll) el.scrollIntoView({ block: 'nearest' });
        });
      }
      function select(name) { ui.selected = name; markSelected(false); paintDetail(); detail.scrollTop = 0; }
      function paintDetail() {
        clear(detail);
        if (!ui.selected) { detail.append(h('div', { class: 'empty' }, icon('table', 34), h('h2', null, 'Elegí una tabla'), h('div', null, 'Verás sus columnas, claves y relaciones.'))); return; }
        detail.append(tableDetail(ui.selected, select));
      }

      const onSearch = debounce(() => { ui.q = search.value; ui.limit = MAX_ROWS; refresh(); }, 120);
      search.addEventListener('input', onSearch);
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { search.value = ''; ui.q = ''; refresh(); return; }
        if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Enter') return;
        e.preventDefault();
        const i = rows.findIndex((r) => r.name === ui.selected);
        const next = e.key === 'ArrowDown' ? Math.min(rows.length - 1, i + 1) : e.key === 'ArrowUp' ? Math.max(0, i - 1) : i;
        if (rows[next]) { select(rows[next].name); markSelected(true); }
      });
      sortSel.addEventListener('change', () => { ui.sort = sortSel.value; refresh(); });

      root.append(h('div', { class: 'explorer' },
        h('div', { class: 'ex-list' },
          h('div', { class: 'ex-tools' },
            h('div', { class: 'searchbox' }, icon('search', 16), search, h('kbd', null, '/')),
            chipsEl,
            h('div', { class: 'ex-count' }, count, sortSel)),
          items),
        detail));
      refresh();
      if (args.focusSearch) search.focus();
    },
  };

  /* ---------------- detalle de una tabla ---------------- */
  function tableDetail(key, select) {
    const S = Etch.state, tables = S.schema.tables, t = tables[key], engine = S.schema.engine;
    const pkCount = t.columns.filter((c) => c.pk).length;
    const fkByCol = new Map(t.relations.map((r) => [r.col, r]));
    const known = (name) => Object.prototype.hasOwnProperty.call(tables, name);
    const tableLink = (name) => known(name)
      ? h('button', { class: 'linkbtn', onclick: () => select(name), title: 'Abrir ' + name }, name)
      : h('span', { class: 'mono muted', title: 'Fuera del esquema escaneado' }, name);

    const colRows = t.columns.map((c, i) => {
      const fk = fkByCol.get(c.name);
      return h('tr', { class: c.pk ? 'pk' : fk ? 'fk' : '' },
        h('td', { class: 'n' }, String(i + 1)),
        h('td', { class: 'nm' }, c.name, ' ',
          c.pk ? h('span', { class: 'badge pk', title: 'Clave primaria' }, icon('key', 11), 'PK') : null, ' ',
          fk ? h('span', { class: 'badge fk', title: 'Clave foránea' }, 'FK') : null),
        h('td', { class: 'ty' }, c.type || '—'),
        h('td', { class: 'nl' + (c.null ? '' : ' no') }, c.null ? 'NULL' : 'NOT NULL'),
        h('td', null, fk ? h('span', { class: 'row', style: { gap: '6px' } }, h('span', { class: 'arrow faint' }, icon('arrow', 13)), tableLink(fk.ref_table), fk.ref_col ? h('span', { class: 'faint mono', style: { fontSize: '12px' } }, '.' + fk.ref_col) : null) : ''));
    });

    const relCard = (title, list, render) => h('div', null,
      h('div', { class: 'sec-title' }, title, h('span', { class: 'badge' }, String(list.length))),
      list.length ? h('div', { class: 'rel' }, list.map(render)) : h('div', { class: 'muted', style: { fontSize: '13px' } }, 'Ninguna.'));

    const copy = async (text, what) => { (await Etch.copyText(text)) ? Etch.toast('success', what + ' copiado', { timeout: 1800 }) : Etch.toast('error', 'No se pudo copiar al portapapeles'); };

    return h('div', { class: 'detail' },
      h('div', { class: 'detail-head' },
        h('div', { class: 'grow' },
          h('h2', { class: 'mono' }, key),
          h('div', { class: 'meta' },
            t.schema ? h('span', { class: 'badge' }, 'esquema ' + t.schema) : null,
            h('span', null, Etch.plural(t.columns.length, 'columna', 'columnas')),
            h('span', null, '·'),
            h('span', null, pkCount ? Etch.plural(pkCount, 'clave primaria', 'claves primarias') : 'sin clave primaria'),
            h('span', null, '·'),
            h('span', null, Etch.plural(t.relations.length + t.referenced_by.length, 'relación', 'relaciones')))),
        h('div', { class: 'row', style: { flexWrap: 'wrap' } },
          h('button', { class: 'btn', onclick: () => Etch.go('map', { focus: key }) }, icon('map', 16), 'Ver en el mapa'),
          h('button', { class: 'btn', onclick: () => copy(key, 'Nombre') }, icon('copy', 16), 'Copiar nombre'),
          h('button', { class: 'btn', onclick: () => copy(Etch.buildDDL(engine, key, t), 'DDL') }, icon('file', 16), 'Copiar DDL'))),

      !pkCount ? h('div', { class: 'banner' }, icon('alert', 18), h('div', { class: 'grow' }, h('b', null, 'Sin clave primaria. '), 'Esta tabla no tiene PK declarada: puede admitir filas duplicadas y dificulta las relaciones.')) : null,

      h('div', { class: 'sec-title' }, 'Columnas'),
      h('table', { class: 'cols' },
        h('thead', null, h('tr', null, ['#', 'Nombre', 'Tipo', 'Nulos', 'Referencia'].map((x) => h('th', null, x)))),
        h('tbody', null, colRows)),

      h('div', { class: 'relgrid' },
        relCard('Referencia a', t.relations, (r) => h('div', { class: 'r' },
          h('span', { class: 'mono' }, r.col), h('span', { class: 'arrow' }, icon('arrow', 14)), tableLink(r.ref_table), r.ref_col ? h('span', { class: 'faint mono' }, '.' + r.ref_col) : null)),
        relCard('Referenciada por', t.referenced_by, (r) => h('div', { class: 'r' },
          tableLink(r.table), h('span', { class: 'faint mono' }, '.' + r.col), h('span', { class: 'arrow' }, icon('arrow', 14)), h('span', { class: 'mono' }, r.ref_col || key)))));
  }
})();
