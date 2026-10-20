/* Resumen: vista general del esquema escaneado. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon } = Etch;

  /* Grupos de tablas conectadas (componentes conexos, ignorando el sentido de la FK). */
  function components(tables) {
    const adj = new Map(Object.keys(tables).map((k) => [k, new Set()]));
    for (const [name, t] of Object.entries(tables)) {
      for (const r of t.relations) {
        if (adj.has(r.ref_table) && r.ref_table !== name) { adj.get(name).add(r.ref_table); adj.get(r.ref_table).add(name); }
      }
    }
    const seen = new Set(), groups = [];
    for (const start of adj.keys()) {
      if (seen.has(start) || adj.get(start).size === 0) continue;
      const comp = [], queue = [start]; seen.add(start);
      while (queue.length) {
        const n = queue.pop(); comp.push(n);
        for (const m of adj.get(n)) if (!seen.has(m)) { seen.add(m); queue.push(m); }
      }
      groups.push(comp);
    }
    return groups.sort((a, b) => b.length - a.length);
  }
  Etch.schemaComponents = components;

  function rank(items, valueLabel) {
    const max = Math.max(1, ...items.map((i) => i.value));
    return h('div', { class: 'rank' }, items.map((i) =>
      h('button', { onclick: () => Etch.openTable(i.name) },
        h('span', { class: 'bar', style: { width: (i.value / max * 100) + '%' } }),
        h('span', { class: 'n mono truncate' }, i.name),
        h('span', { class: 'v' }, i.value + ' ' + valueLabel))));
  }

  Etch.views.overview = {
    render(root) {
      const S = Etch.state, sc = S.schema, t = sc.tables, m = sc.meta;
      const names = Object.keys(t);
      const conn = S.connections.find((c) => c.alias === S.alias) || {};
      const degree = (n) => t[n].relations.length + t[n].referenced_by.length;

      const hubs = names.map((n) => ({ name: n, value: degree(n) })).filter((x) => x.value > 0).sort((a, b) => b.value - a.value).slice(0, 8);
      const wide = names.map((n) => ({ name: n, value: t[n].columns.length })).sort((a, b) => b.value - a.value).slice(0, 8);
      const noPk = names.filter((n) => !t[n].columns.some((c) => c.pk));
      const groups = components(t);

      const stat = (ico, num, label, onclick) =>
        h('div', { class: 'card stat' + (onclick ? ' click' : ''), onclick, role: onclick ? 'button' : null, tabindex: onclick ? '0' : null },
          h('span', { class: 'ico' }, icon(ico, 22)), h('div', { class: 'num' }, Etch.num(num)), h('div', { class: 'lab' }, label));

      root.append(h('div', { class: 'page' },
        h('h1', null, 'Resumen'),
        h('p', { class: 'lead' }, 'Vista general del esquema de ', h('b', null, S.alias), '. Hacé clic en una tarjeta para profundizar.'),

        h('div', { class: 'grid stats' },
          stat('table', m.table_count, 'Tablas', () => Etch.go('explorer', { filter: 'all' })),
          stat('layers', m.column_count, 'Columnas', () => Etch.go('explorer', { filter: 'all', sort: 'columns' })),
          stat('link', m.relation_count, 'Relaciones (FK)', () => Etch.go('map')),
          stat('folder', m.orphan_count, 'Tablas huérfanas', () => Etch.go('explorer', { filter: 'orphans' }))),

        m.relation_count === 0 && m.table_count > 0 ? h('div', { class: 'banner' }, icon('info', 18),
          h('div', { class: 'grow' }, h('b', null, 'Esta base no declara claves foráneas. '),
            'Las relaciones solo se dibujan si están definidas como FOREIGN KEY en la base; es común en bases antiguas, donde el vínculo existe solo por convención (por ejemplo, una columna ',
            h('code', null, 'ClientID'), '). El Explorador y la búsqueda funcionan igual.')) : null,

        h('div', { class: 'grid two' },
          h('div', { class: 'card' }, h('h3', null, 'Tablas más conectadas'),
            hubs.length ? rank(hubs, 'rel.') : h('div', { class: 'muted' }, 'Sin relaciones declaradas.')),
          h('div', { class: 'card' }, h('h3', null, 'Tablas con más columnas'), rank(wide, 'col.'))),

        h('div', { class: 'grid two' },
          h('div', { class: 'card' }, h('h3', null, 'Grupos de tablas relacionadas'),
            groups.length ? h('div', null,
              h('p', { style: { margin: '0 0 10px' } }, h('b', null, groups.length), ' grupo' + (groups.length === 1 ? '' : 's') + ' (el mayor tiene ', h('b', null, groups[0].length), ' tablas).'),
              h('div', { class: 'muted', style: { fontSize: '12.5px' } }, 'Cada grupo es un conjunto de tablas conectadas entre sí por claves foráneas. En el mapa se ven con colores distintos.'),
              h('div', { style: { marginTop: '12px' } }, h('button', { class: 'btn', onclick: () => Etch.go('map') }, icon('map', 16), 'Abrir el mapa')))
              : h('div', { class: 'muted' }, 'No hay grupos: ninguna tabla se relaciona con otra.')),
          h('div', { class: 'card' }, h('h3', null, 'Calidad del esquema'),
            h('div', { class: 'row', style: { marginBottom: '8px' } },
              h('span', { class: 'badge ' + (noPk.length ? 'warn' : 'good') }, noPk.length ? 'Atención' : 'Bien'),
              h('span', null, noPk.length ? Etch.plural(noPk.length, 'tabla sin clave primaria', 'tablas sin clave primaria') : 'Todas las tablas tienen clave primaria')),
            noPk.length ? h('div', { class: 'rank' }, noPk.slice(0, 6).map((n) => h('button', { onclick: () => Etch.openTable(n) },
              h('span', { class: 'n mono truncate' }, n), h('span', { class: 'v' }, 'sin PK')))) : null,
            noPk.length > 6 ? h('div', { class: 'faint', style: { marginTop: '8px', fontSize: '12.5px' } }, 'y ' + (noPk.length - 6) + ' más (filtro «Sin PK» en el Explorador).') : null)),

        h('div', { class: 'card' }, h('h3', null, 'Conexión'),
          h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '22px' } },
            kv('Motor', Etch.engineLabel(sc.engine)),
            kv('Último escaneo', Etch.fmtDate(sc.last_scan)),
            kv('Duración', Etch.fmtDuration(sc.duration_sec)),
            kv('Destino', conn.masked_uri || '—', true),
            h('div', { class: 'grow' }),
            h('button', { class: 'btn', onclick: () => Etch.scan(S.alias) }, icon('refresh', 16), 'Reescanear'),
            h('button', { class: 'btn', onclick: () => exportJson(sc, S.alias) }, icon('download', 16), 'Exportar esquema (JSON)')))));
    },
  };

  function kv(k, v, mono) {
    return h('div', { style: { minWidth: 0 } }, h('div', { class: 'faint', style: { fontSize: '11px', textTransform: 'uppercase', letterSpacing: '.08em', fontWeight: 700 } }, k),
      h('div', { class: mono ? 'mono truncate' : '', style: { marginTop: '2px' } }, v));
  }

  async function exportJson(sc, alias) {
    const payload = { exported_by: 'Etch-DB-Mapper ' + Etch.state.version, connection: alias, engine: sc.engine, scanned_at: sc.last_scan, meta: sc.meta, tables: sc.tables };
    const r = await Etch.api.save_file(alias.replace(/[^\w.-]+/g, '_') + '_esquema.json', JSON.stringify(payload, null, 2));
    if (r.ok) Etch.toast('success', 'Esquema exportado', { detail: r.path });
    else if (!r.cancelled) Etch.toast('error', 'No se pudo exportar', { detail: r.error });
  }
})();
