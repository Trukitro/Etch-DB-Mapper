/* Rutas: cómo unir dos tablas. Busca los caminos más cortos por claves foráneas (y, si se
   quiere, relaciones probables) y genera el SQL del JOIN. Solo genera texto. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon } = Etch;

  const ui = { from: '', to: '', inferred: true, alias: null };

  Etch.views.paths = {
    render(root, args) {
      const S = Etch.state, tables = S.schema.tables, names = Object.keys(tables).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
      if (ui.alias !== S.alias) Object.assign(ui, { from: '', to: '', alias: S.alias });
      if (args.from && tables[args.from]) { ui.from = args.from; if (args.to && tables[args.to]) ui.to = args.to; else if (args.from !== ui.to) ui.to = ''; }
      const hasInferred = (S.schema.inferred || []).length > 0;

      const list = h('datalist', { id: 'path-tables' }, names.map((n) => h('option', { value: n })));
      const fromIn = h('input', { class: 'input mono', list: 'path-tables', placeholder: 'Tabla de origen', value: ui.from, 'aria-label': 'Tabla de origen', autocomplete: 'off', spellcheck: 'false' });
      const toIn = h('input', { class: 'input mono', list: 'path-tables', placeholder: 'Tabla de destino', value: ui.to, 'aria-label': 'Tabla de destino', autocomplete: 'off', spellcheck: 'false' });
      const swap = h('button', { class: 'btn icon-only', title: 'Intercambiar', 'aria-label': 'Intercambiar origen y destino', onclick: () => { const a = fromIn.value; fromIn.value = toIn.value; toIn.value = a; search(); } }, icon('refresh', 15));
      const inf = h('input', { type: 'checkbox', id: 'path-inf', checked: ui.inferred, disabled: !hasInferred });
      const out = h('div');
      const goBtn = h('button', { class: 'btn primary', onclick: () => search() }, icon('route', 16), 'Buscar caminos');

      const hint = (text, kind) => h('div', { class: 'card empty' }, icon(kind || 'route', 32), h('h2', null, text.title), h('div', { style: { maxWidth: '56ch', margin: '0 auto' } }, text.body));

      async function search() {
        ui.from = fromIn.value.trim(); ui.to = toIn.value.trim(); ui.inferred = inf.checked;
        out.replaceChildren();
        if (!ui.from || !ui.to) { out.append(hint({ title: 'Elige dos tablas', body: 'Escribe o selecciona la tabla de origen y la de destino. Verás cómo unirlas y el SQL listo para copiar.' })); return; }
        if (!tables[ui.from] || !tables[ui.to]) { out.append(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, 'Una de las tablas no existe en el esquema. Elige una de la lista.'))); return; }
        if (ui.from === ui.to) { out.append(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, 'Elige dos tablas distintas.'))); return; }
        out.append(h('div', { class: 'skeleton', style: { height: '110px' } }));
        const r = await Etch.api.find_paths(S.alias, ui.from, ui.to, ui.inferred);
        out.replaceChildren();
        if (!r.ok) { out.append(h('div', { class: 'banner bad' }, icon('alert', 18), h('div', { class: 'grow' }, r.error))); return; }
        if (!r.paths.length) {
          out.append(hint({ title: 'No hay un camino conocido', body: 'Estas tablas no se conectan por claves foráneas' + (ui.inferred ? ' ni por relaciones probables' : '') + '. '
            + (!ui.inferred && hasInferred ? 'Prueba activando «Incluir relaciones probables». ' : '') + 'Puede que se relacionen por columnas que no comparten nombre; revísalo en el Explorador.' }, 'link'));
          return;
        }
        out.append(h('div', { class: 'muted', style: { margin: '4px 0 12px' } }, Etch.plural(r.paths.length, 'camino encontrado', 'caminos encontrados') + ' (los más cortos y con claves reales primero).'));
        r.paths.forEach((p, i) => out.append(pathCard(p, i)));
      }

      function pathCard(p, i) {
        const first = p.steps[0].left;
        const chain = h('div', { class: 'chain' }, nodeBtn(first));
        p.steps.forEach((st) => {
          chain.append(h('span', { class: 'hop' + (st.inferred ? ' inferred' : ''), title: st.inferred ? 'Relación probable (deducida por nombre)' : 'Clave foránea declarada' },
            st.left_col + (st.left_col === st.right_col ? '' : ' = ' + st.right_col), icon('arrow', 14)), nodeBtn(st.right));
        });
        const names = [first].concat(p.steps.map((s) => s.right));
        return h('div', { class: 'card path-card' },
          h('div', { class: 'row', style: { justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' } },
            h('div', { class: 'row' }, h('b', null, 'Camino ' + (i + 1)), h('span', { class: 'badge' }, Etch.plural(p.length, 'salto', 'saltos')),
              p.inferred ? h('span', { class: 'badge warn', title: 'Alguna unión se deduce por nombre; no es una clave foránea real' }, p.inferred + ' probable' + (p.inferred > 1 ? 's' : '')) : h('span', { class: 'badge good' }, 'solo claves reales')),
            h('div', { class: 'row' },
              h('button', { class: 'btn sm', onclick: async () => { if (await Etch.copyText(p.sql)) Etch.toast('success', 'SQL copiado', { timeout: 1800 }); } }, icon('copy', 14), 'Copiar SQL'),
              h('button', { class: 'btn sm', onclick: async () => { if (p.inferred && !S.settings.map_show_inferred) await Etch.saveSetting('map_show_inferred', true); Etch.go('map', { path: names }); } }, icon('map', 14), 'Ver en el mapa'))),
          chain, h('pre', { class: 'sql' }, p.sql));
      }
      const nodeBtn = (n) => h('button', { class: 'node', title: 'Abrir ' + n + ' en el Explorador', onclick: () => Etch.openTable(n) }, n);

      [fromIn, toIn].forEach((el) => el.addEventListener('keydown', (e) => { if (e.key === 'Enter') search(); }));
      [fromIn, toIn].forEach((el) => el.addEventListener('change', () => { if (fromIn.value && toIn.value) search(); }));
      inf.addEventListener('change', () => { if (fromIn.value && toIn.value) search(); });

      root.append(h('div', { class: 'page' },
        h('h1', null, 'Rutas entre tablas'),
        h('p', { class: 'lead' }, '¿Cómo uno ', h('b', null, 'Pedidos'), ' con ', h('b', null, 'Conductores'), '? Elige dos tablas y obtén los caminos por claves foráneas, con el SQL del JOIN para copiar. La app solo genera el texto: no ejecuta nada en tu base.'),
        list,
        h('div', { class: 'path-pickers' },
          h('div', { class: 'field', style: { margin: 0 } }, h('label', null, 'Desde'), fromIn), swap, h('div', { class: 'field', style: { margin: 0 } }, h('label', null, 'Hasta'), toIn)),
        h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '14px', marginBottom: '16px' } }, goBtn,
          h('label', { class: 'check', for: 'path-inf', style: { margin: 0 } }, inf,
            h('span', null, hasInferred ? 'Incluir relaciones probables (deducidas por nombre)' : 'No hay relaciones probables en este esquema'))),
        out));
      search();
    },
  };
})();
