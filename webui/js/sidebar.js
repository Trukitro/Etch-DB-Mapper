/* Barra lateral: marca, conexiones guardadas, accesos a Ayuda/Novedades, tema. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon, $, clear } = Etch;

  /* ---------------- menú contextual ---------------- */
  let menuEl = null;
  function closeMenu() { if (menuEl) { menuEl.remove(); menuEl = null; } }
  function openMenu(x, y, items) {
    closeMenu();
    menuEl = h('div', { class: 'menu', role: 'menu' }, items.map((it) =>
      it === '-' ? h('hr') :
      h('button', { role: 'menuitem', class: it.danger ? 'danger' : '', onclick: () => { closeMenu(); it.run(); } },
        icon(it.icon, 16), it.label)));
    document.body.append(menuEl);
    const r = menuEl.getBoundingClientRect();
    menuEl.style.left = Math.min(x, window.innerWidth - r.width - 8) + 'px';
    menuEl.style.top = Math.min(y, window.innerHeight - r.height - 8) + 'px';
    menuEl.querySelector('button').focus();
  }
  document.addEventListener('mousedown', (e) => { if (menuEl && !menuEl.contains(e.target)) closeMenu(); }, true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); }, true);
  window.addEventListener('blur', closeMenu);
  Etch.openMenu = openMenu;

  function connMenu(c) {
    return [
      { icon: 'refresh', label: 'Reescanear', run: () => Etch.scan(c.alias) },
      { icon: 'link', label: 'Editar conexión…', run: () => Etch.dialogs.connection({ alias: c.alias }) },
      { icon: 'edit', label: 'Renombrar…', run: () => Etch.dialogs.rename(c.alias) },
      '-',
      { icon: 'trash', label: 'Eliminar…', danger: true, run: () => Etch.deleteConnection(c.alias) },
    ];
  }

  /* ---------------- conexión ---------------- */
  function connItem(c) {
    const S = Etch.state;
    const active = S.alias === c.alias && ['overview', 'explorer', 'map'].includes(S.view);
    const dot = c.scan ? 'busy' : c.status === 'error' ? 'err' : c.status === 'success' ? 'ok' : '';
    let sub;
    if (c.scan) sub = h('span', { class: 'truncate', 'data-scan-msg': c.alias }, c.scan.message || 'Escaneando…');
    else if (c.status === 'error') sub = h('span', { class: 'truncate', style: { color: 'var(--bad)' } }, 'Error de conexión');
    else if (!c.has_data) sub = h('span', { class: 'faint' }, 'Sin escanear');
    else sub = h('span', { class: 'truncate' }, Etch.plural(c.table_count, 'tabla', 'tablas') + ' · ' + Etch.relTime(c.last_scan));

    const el = h('div', {
      class: 'conn' + (active ? ' active' : ''), role: 'listitem', tabindex: '0',
      title: c.alias + '\n' + c.masked_uri,
      onclick: () => Etch.selectConnection(c.alias),
      onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); Etch.selectConnection(c.alias); } },
      oncontextmenu: (e) => { e.preventDefault(); openMenu(e.clientX, e.clientY, connMenu(c)); },
    },
      h('div', { class: 'avatar' }, (c.alias.trim()[0] || '?').toUpperCase(), h('span', { class: 'dot ' + dot })),
      h('div', { class: 'txt grow' },
        h('div', { class: 't truncate' }, c.alias),
        h('div', { class: 's' }, h('span', { class: 'badge eng' }, Etch.engineShort(c.engine)), sub)),
      h('div', { class: 'actions' },
        h('button', { class: 'btn icon-only ghost', title: 'Reescanear', 'aria-label': 'Reescanear ' + c.alias,
          onclick: (e) => { e.stopPropagation(); Etch.scan(c.alias); } }, icon('refresh', 15)),
        h('button', { class: 'btn icon-only ghost', title: 'Más acciones', 'aria-label': 'Más acciones para ' + c.alias,
          onclick: (e) => { e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); openMenu(r.left, r.bottom + 4, connMenu(c)); } }, icon('dots', 15))));
    return el;
  }

  const THEME_ICON = { dark: 'moon', light: 'sun', system: 'monitor' };
  const THEME_LABEL = { dark: 'Tema oscuro', light: 'Tema claro', system: 'Tema del sistema' };

  function navbtn(iconName, label, view) {
    const active = Etch.state.view === view;
    return h('button', { class: 'btn ghost navbtn' + (active ? ' active' : ''), onclick: () => Etch.go(view), title: label },
      icon(iconName, 17), h('span', { class: 'label' }, label));
  }

  function renderSidebar() {
    const S = Etch.state;
    const el = clear($('#sidebar'));
    $('#app').classList.toggle('collapsed', !!S.settings.sidebar_collapsed);
    el.append(
      h('div', { class: 'brand', style: { cursor: 'pointer' }, onclick: () => Etch.go('home'), title: 'Inicio' },
        h('img', { src: 'assets/icon.svg', alt: '' }),
        h('div', { class: 'txt' },
          h('div', { class: 'name' }, 'Etch-DB-', h('b', null, 'Mapper')),
          h('div', { class: 'ver' }, 'v' + S.version))),
      h('button', { class: 'btn primary new', onclick: () => Etch.dialogs.connection(), title: 'Nueva conexión (Ctrl+N)' },
        icon('plus', 17), h('span', { class: 'label' }, 'Nueva conexión')),
      h('div', { class: 'side-label' }, 'Conexiones'),
      h('div', { class: 'conn-list', role: 'list' },
        S.connections.length
          ? S.connections.map(connItem)
          : h('div', { class: 'faint', style: { padding: '10px 12px', fontSize: '12.5px' } }, 'Todavía no guardaste ninguna conexión.')),
      h('div', { class: 'foot' },
        navbtn('help', 'Ayuda', 'help'),
        navbtn('file', 'Novedades', 'changelog'),
        h('div', { class: 'row', style: { justifyContent: 'space-between', padding: '2px 4px 0' } },
          h('button', { class: 'btn ghost sm', title: THEME_LABEL[S.settings.theme] + ' (clic para cambiar)', 'aria-label': 'Cambiar tema',
            onclick: () => Etch.cycleTheme() }, icon(THEME_ICON[S.settings.theme] || 'moon', 16), h('span', { class: 'label' }, THEME_LABEL[S.settings.theme])),
          h('button', { class: 'btn ghost icon-only', title: 'Colapsar / expandir la barra', 'aria-label': 'Colapsar barra lateral',
            onclick: () => Etch.toggleSidebar() }, icon('sidebar', 16)))));
  }
  Etch.renderSidebar = renderSidebar;
})();
