/* Ayuda y Novedades: renderizan HELP.md y CHANGELOG.md (empaquetados con la app). */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon, $ } = Etch;

  const cache = {};
  let observer = null;

  async function load(kind) {
    if (cache[kind]) return cache[kind];
    const r = await (kind === 'help' ? Etch.api.get_help() : Etch.api.get_changelog());
    cache[kind] = Etch.renderMarkdown(r.markdown || '');
    return cache[kind];
  }

  function mount(kind, root, args) {
    const prose = h('article', { class: 'prose' + (kind === 'changelog' ? ' changelog' : '') }, h('div', { class: 'skeleton', style: { height: '200px' } }));
    const toc = h('nav', { class: 'toc', 'aria-label': 'Contenido' });
    root.append(h('div', { class: 'docs' }, toc, prose));

    load(kind).then((doc) => {
      prose.innerHTML = doc.html; // el HTML sale de nuestro renderMarkdown: todo el texto va escapado
      if (kind === 'help') {
        const actions = h('div', { class: 'row', style: { flexWrap: 'wrap', margin: '14px 0 4px' } },
          h('button', { class: 'btn primary', onclick: () => Etch.dialogs.connection() }, icon('plus', 16), 'Nueva conexión'),
          h('button', { class: 'btn', onclick: async () => {
            const r = await Etch.api.create_demo_connection();
            if (!r.ok) return Etch.toast('error', r.error);
            await Etch.refreshConnections(); Etch.selectConnection(r.alias); Etch.scan(r.alias);
          } }, icon('zap', 16), 'Probar con la base de ejemplo'),
          Etch.state.repoUrl ? h('a', { class: 'btn', href: Etch.state.repoUrl }, icon('external', 16), 'Repositorio y reporte de errores') : null);
        const h1 = prose.querySelector('h1');
        if (h1) h1.after(actions);
      }
      if (kind === 'changelog') {
        prose.querySelectorAll('h2').forEach((el) => {
          if (el.textContent.includes(Etch.state.version)) el.append(' ', h('span', { class: 'badge good' }, 'instalada'));
        });
      }
      toc.append(h('b', null, kind === 'help' ? 'En esta guía' : 'Versiones'),
        ...doc.headings.map((hd) => h('a', { href: '#' + hd.id, 'data-id': hd.id }, hd.text.replace(/^\[|\]$/g, ''))));

      if (window.IntersectionObserver) {
        observer = new IntersectionObserver((entries) => {
          entries.forEach((en) => {
            if (!en.isIntersecting) return;
            toc.querySelectorAll('a').forEach((a) => { a.style.color = ''; a.style.borderLeftColor = ''; });
            const a = toc.querySelector('a[data-id="' + en.target.id + '"]');
            if (a) { a.style.color = 'var(--accent)'; a.style.borderLeftColor = 'var(--accent)'; }
          });
        }, { root: $('#view'), rootMargin: '0px 0px -75% 0px' });
        prose.querySelectorAll('h2').forEach((el) => observer.observe(el));
      }
      if (args && args.anchor) {
        const t = document.getElementById(args.anchor);
        if (t) setTimeout(() => t.scrollIntoView({ block: 'start' }), 30);
      }
    }).catch((e) => {
      prose.textContent = 'No se pudo cargar el documento: ' + (e && e.message || e);
    });
  }

  const destroy = () => { if (observer) { observer.disconnect(); observer = null; } };
  Etch.views.help = { render: (root, args) => mount('help', root, args), destroy };
  Etch.views.changelog = { render: (root, args) => mount('changelog', root, args), destroy };
})();
