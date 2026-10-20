/* Notificaciones flotantes ("toast") estilo SweetAlert / flash de web2py.
   Viven en un contenedor position:fixed: NO ocupan lugar en el layout, así
   que al desaparecer no dejan ningún hueco. Se apilan, se cierran solas y
   se pausan al pasar el mouse por encima. */
(function () {
  'use strict';
  const { h, icon } = window.Etch;
  const ICON = { success: 'check', error: 'alert', info: 'info', warning: 'alert' };
  const DEFAULT_MS = { success: 4000, info: 4500, warning: 7000, error: 10000 };
  const MAX_VISIBLE = 4;

  /* toast('success'|'error'|'info'|'warning', 'Título', { detail, timeout, copy }) */
  function toast(type, title, opts) {
    opts = opts || {};
    const root = document.getElementById('toasts');
    const ms = opts.timeout != null ? opts.timeout : DEFAULT_MS[type] || 4500;
    let timer = null, remaining = ms, startedAt = 0;

    const life = h('div', { class: 'life', style: { animationDuration: ms + 'ms' } });
    const el = h('div', { class: 'toast ' + type, role: type === 'error' ? 'alert' : 'status' },
      h('span', { class: 'ico' }, icon(ICON[type] || 'info', 20)),
      h('div', null,
        h('div', { class: 'tt' }, title),
        opts.detail ? h('div', { class: 'dd' }, opts.detail) : null,
        opts.detail && opts.copy !== false && type === 'error'
          ? h('button', { class: 'btn sm ghost', style: { marginTop: '6px', paddingLeft: '0' },
              onclick: async () => { await window.Etch.copyText(opts.detail); toast('info', 'Detalle copiado', { timeout: 1800 }); } },
              icon('copy', 14), 'Copiar detalle')
          : null),
      h('button', { class: 'btn icon-only ghost', 'aria-label': 'Cerrar', onclick: () => dismiss() }, icon('x', 16)),
      life);

    function dismiss() {
      clearTimeout(timer);
      if (!el.isConnected) return;
      el.classList.add('out');
      setTimeout(() => el.remove(), 260);
    }
    function start() { startedAt = Date.now(); timer = setTimeout(dismiss, remaining); life.style.animationPlayState = 'running'; }
    function pause() { clearTimeout(timer); remaining -= Date.now() - startedAt; life.style.animationPlayState = 'paused'; }
    el.addEventListener('mouseenter', pause);
    el.addEventListener('mouseleave', () => { remaining = Math.max(remaining, 1500); start(); });

    root.prepend(el);
    while (root.children.length > MAX_VISIBLE) root.lastElementChild.remove();
    start();
    return { dismiss };
  }

  window.Etch.toast = toast;
})();
