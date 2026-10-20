/* Puente con el backend Python.

   - Dentro de la app: window.pywebview.api.<método>(...) (lo inyecta pywebview).
   - Abierto en un navegador normal (desarrollo/diseño, `python -m http.server`
     sobre webui/): no existe pywebview, así que se carga js/dev/mock-api.js,
     una API simulada con datos de ejemplo. Sirve para iterar la UI y probarla
     sin ventana nativa.

   Eventos Python -> JS: el backend llama window.EtchBridge.emit(evento, datos). */
(function () {
  'use strict';
  const Etch = window.Etch;
  const listeners = {};

  window.EtchBridge = {
    emit(event, payload) {
      (listeners[event] || []).forEach((fn) => {
        try { fn(payload); } catch (e) { console.error('[bridge]', event, e); }
      });
    },
  };
  Etch.on = (event, fn) => { (listeners[event] = listeners[event] || []).push(fn); };

  let readyPromise = null;
  function loadMock() {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'js/dev/mock-api.js';
      s.onload = () => resolve(window.EtchMockApi);
      s.onerror = () => reject(new Error('No se pudo cargar la API simulada'));
      document.head.append(s);
    });
  }
  function ready() {
    if (readyPromise) return readyPromise;
    readyPromise = new Promise((resolve, reject) => {
      const started = Date.now();
      const poll = () => {
        if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
        if (Date.now() - started > 1200 && !window.pywebview) {
          Etch.devMode = true;
          return loadMock().then(resolve, reject);
        }
        setTimeout(poll, 40);
      };
      poll();
    });
    return readyPromise;
  }

  /* Etch.api.metodo(...args) -> Promise con el dict que devuelve Python. */
  Etch.api = new Proxy({}, {
    get: (_t, name) => async (...args) => {
      const api = await ready();
      if (typeof api[name] !== 'function') throw new Error('Método inexistente en la API: ' + name);
      return api[name](...args);
    },
  });

  /* Errores no atrapados -> etch.log (la app empaquetada no tiene consola). */
  function report(msg) {
    console.error(msg);
    try { Etch.api.log_js('error', msg).catch(() => {}); } catch (e) { /* nada */ }
  }
  window.addEventListener('error', (e) => report('error: ' + e.message + ' @ ' + (e.filename || '') + ':' + e.lineno));
  window.addEventListener('unhandledrejection', (e) => report('promesa rechazada: ' + (e.reason && e.reason.message || e.reason)));
})();
