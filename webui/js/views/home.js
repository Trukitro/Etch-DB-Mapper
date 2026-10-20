/* Vista de inicio / onboarding. Se ve cuando no hay una conexión seleccionada. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon } = Etch;

  async function tryDemo(btn) {
    btn.disabled = true;
    const r = await Etch.api.create_demo_connection();
    if (!r.ok) { btn.disabled = false; return Etch.toast('error', 'No se pudo crear la base de ejemplo', { detail: r.error }); }
    await Etch.refreshConnections();
    Etch.selectConnection(r.alias);
    Etch.scan(r.alias);
  }

  Etch.views.home = {
    render(root) {
      const S = Etch.state;
      const conns = S.connections;
      const demoBtn = h('button', { class: 'btn', onclick: (e) => tryDemo(e.currentTarget) }, icon('zap', 16), 'Probar con una base de ejemplo');

      root.append(h('div', { class: 'page' },
        h('div', { class: 'hero' },
          h('div', { class: 'row', style: { gap: '14px' } }, h('img', { src: 'assets/icon.svg', alt: '', width: 54, height: 54 }),
            h('h1', null, conns.length ? 'Bienvenido de nuevo' : 'Mapeá tu base de datos')),
          h('p', null, 'Etch-DB-Mapper lee el esquema de tu base —tablas, columnas, claves y relaciones— y te lo muestra como un explorador y un mapa interactivo. Solo lee metadatos: nunca modifica tus datos.'),
          h('div', { class: 'row', style: { gap: '10px', flexWrap: 'wrap' } },
            h('button', { class: 'btn primary', onclick: () => Etch.dialogs.connection() }, icon('plus', 16), 'Nueva conexión'),
            demoBtn,
            h('button', { class: 'btn ghost', onclick: () => Etch.go('help') }, icon('help', 16), 'Leer la guía'))),

        h('div', { class: 'steps' },
          step(1, 'Conectá', 'Pegá la URI de tu base (PostgreSQL, SQL Server, MySQL, SQLite…). Se guarda al instante, aunque falle.'),
          step(2, 'Escaneá', 'Un clic lee el esquema completo en unos segundos, con progreso a la vista.'),
          step(3, 'Explorá', 'Buscá tablas y columnas, seguí las relaciones y abrí el mapa para ver el panorama.')),

        conns.length ? h('div', null,
          h('div', { class: 'sec-title' }, 'Tus conexiones'),
          h('div', { class: 'recent' }, conns.map((c) =>
            h('button', { class: 'card stat click', style: { textAlign: 'left', cursor: 'pointer' }, onclick: () => Etch.selectConnection(c.alias) },
              h('div', { class: 'row' }, h('b', { class: 'truncate grow' }, c.alias), h('span', { class: 'badge eng' }, Etch.engineShort(c.engine))),
              h('div', { class: 'muted', style: { marginTop: '6px', fontSize: '12.5px' } },
                c.has_data ? Etch.plural(c.table_count, 'tabla', 'tablas') + ' · ' + Etch.plural(c.relation_count, 'relación', 'relaciones') : (c.status === 'error' ? 'Error de conexión' : 'Sin escanear')),
              h('div', { class: 'faint', style: { fontSize: '12px', marginTop: '2px' } }, 'Último escaneo: ' + Etch.relTime(c.last_scan)))))) : null));
    },
  };

  function step(n, title, text) {
    return h('div', { class: 'card step' }, h('div', { class: 'n' }, String(n)), h('b', null, title), h('span', null, text));
  }
})();
