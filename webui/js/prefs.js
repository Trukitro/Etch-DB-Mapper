/* Preferencias: tema, actualizaciones, seguridad de las contraseñas y datos. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon } = Etch;

  Etch.dialogs.preferences = async () => {
    const S = Etch.state;
    const boot = await Etch.api.security_status();
    const themeSel = h('select', { class: 'select', style: { width: '170px' }, 'aria-label': 'Tema' },
      [['dark', 'Oscuro'], ['light', 'Claro'], ['system', 'Del sistema']].map(([v, l]) => h('option', { value: v, selected: S.settings.theme === v }, l)));
    themeSel.addEventListener('change', () => { S.settings.theme = themeSel.value; Etch.applyTheme(); Etch.renderChrome(); Etch.api.save_settings({ theme: themeSel.value }); });

    const upd = h('input', { type: 'checkbox', id: 'pref-upd', checked: !!S.settings.check_updates, disabled: !!S.updateBlocked });
    upd.addEventListener('change', () => Etch.saveSetting('check_updates', upd.checked));
    const updOut = h('div', { class: 'hint', style: { minHeight: '18px', marginTop: '6px' } });
    const updBtn = h('button', { class: 'btn sm', onclick: async () => {
      updBtn.disabled = true; updOut.className = 'hint'; updOut.textContent = 'Consultando GitHub…';
      const r = await Etch.api.check_updates(true);
      updBtn.disabled = false;
      if (!r.ok) { updOut.className = 'hint warn'; updOut.textContent = r.error; return; }
      if (r.newer) { Etch.setUpdate(r); updOut.className = 'hint good'; updOut.textContent = 'Hay una versión nueva: ' + r.latest + ' (tienes ' + r.current + ').'; }
      else { updOut.className = 'hint good'; updOut.textContent = 'Estás al día (versión ' + r.current + ').'; }
    } }, icon('refresh', 14), 'Buscar ahora');

    const sec = boot;
    const secBadge = h('span', { class: 'badge ' + (sec.available ? 'good' : 'warn') }, sec.available ? 'Cifrado activo' : 'Sin cifrar');
    const dir = h('code', { class: 'mono truncate', style: { maxWidth: '300px' }, title: S.dataDir }, S.dataDir);

    Etch.modal({
      title: 'Preferencias', width: '600px',
      body: h('div', null,
        h('div', { class: 'pref-section' }, h('h3', null, 'Apariencia'),
          h('div', { class: 'pref-row' }, h('div', null, 'Tema'), themeSel)),
        h('div', { class: 'pref-section' }, h('h3', null, 'Seguridad de las contraseñas'),
          h('div', { class: 'pref-row' }, h('div', null, h('b', null, 'Contraseñas guardadas '), secBadge,
            h('small', null, sec.label + (sec.connections_with_password ? ' Conexiones con contraseña cifradas: ' + sec.encrypted + ' de ' + sec.connections_with_password + '.' : ' Todavía no hay conexiones con contraseña.')))),
          h('div', { class: 'hint', style: { marginTop: '6px' } }, 'La app solo lee metadatos y no envía tus datos a ningún servidor. Más detalles en SECURITY.md del repositorio.')),
        h('div', { class: 'pref-section' }, h('h3', null, 'Actualizaciones'),
          h('div', { class: 'pref-row' }, h('label', { for: 'pref-upd', style: { cursor: 'pointer' } }, 'Avisarme cuando haya una versión nueva',
            h('small', null, S.updateBlocked ? 'Desactivado por la variable de entorno ETCH_NO_UPDATE_CHECK.' : 'Hace una sola consulta pública a GitHub como máximo una vez al día. No envía datos tuyos y nunca instala nada solo.')), upd),
          h('div', { class: 'row' }, updBtn), updOut),
        h('div', { class: 'pref-section' }, h('h3', null, 'Tus datos'),
          h('div', { class: 'pref-row' }, h('div', null, 'Carpeta de datos', h('small', null, 'Conexiones, historial de versiones, ajustes y registro.')),
            h('div', { class: 'row', style: { minWidth: 0 } }, dir, h('button', { class: 'btn sm', onclick: () => Etch.api.open_data_folder() }, icon('folder', 14), 'Abrir')))),
        h('div', { class: 'pref-section', style: { marginBottom: 0 } }, h('h3', null, 'Acerca de'),
          h('div', { class: 'muted', style: { fontSize: '13px' } }, 'Etch-DB-Mapper v' + S.version + ' · ',
            h('a', { href: S.repoUrl }, 'repositorio'), ' · licencias de terceros en THIRD_PARTY_NOTICES.md'))),
      buttons: [{ label: 'Cerrar', kind: 'primary' }],
    });
  };
})();
