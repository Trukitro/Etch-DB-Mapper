/* Mapa relacional (Cytoscape.js + fcose).
   - Alcances: solo tablas relacionadas / todas (huérfanas en una grilla aparte) / vecindad de una tabla.
   - Posiciones persistidas por conexión (map.positions): arrastrar y soltar se recuerda.
   - Hover = modo foco (atenúa todo salvo la vecindad); clic = panel de detalle. */
(function () {
  'use strict';
  const Etch = window.Etch;
  const { h, icon, $, clear, debounce } = Etch;

  const LAYOUTS = [['fcose', 'Fuerzas (recomendado)'], ['breadthfirst', 'Jerárquico'], ['concentric', 'Concéntrico'], ['circle', 'Círculo'], ['grid', 'Grilla']];
  let fcoseReady = false;

  const ui = { alias: null, scope: null, depth: 2, layout: null, focus: null, selected: null };
  let cy = null, ro = null, onResize = null;
  const view = { tables: {} };   // esquema efectivo del mapa (con o sin relaciones inferidas)

  /* Copia del esquema con las relaciones inferidas añadidas (marcadas inferred) para que el
     resto del mapa (grados, grupos, vecindad, panel) las trate como una relación más. */
  function withInferred(tables, inferred) {
    const out = {};
    for (const [n, t] of Object.entries(tables)) out[n] = Object.assign({}, t, { relations: t.relations.slice(), referenced_by: t.referenced_by.slice() });
    for (const r of inferred) {
      if (!out[r.table] || !out[r.ref_table]) continue;
      out[r.table].relations.push({ col: r.col, ref_table: r.ref_table, ref_col: r.ref_col, inferred: true, confidence: r.confidence, reason: r.reason });
      out[r.ref_table].referenced_by.push({ table: r.table, col: r.col, ref_col: r.ref_col, inferred: true });
    }
    return out;
  }

  const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const isLight = () => document.documentElement.getAttribute('data-theme') === 'light';

  function ensureFcose() {
    if (fcoseReady) return;
    try { if (window.cytoscapeFcose) window.cytoscape.use(window.cytoscapeFcose); } catch (e) { console.warn('fcose', e); }
    fcoseReady = true;
  }

  /* ---------------- datos ---------------- */
  function degreeMap(tables) {
    const deg = {};
    for (const [n, t] of Object.entries(tables)) {
      deg[n] = t.relations.filter((r) => tables[r.ref_table]).length + t.referenced_by.filter((r) => tables[r.table]).length;
    }
    return deg;
  }
  function neighborhood(tables, start, depth) {
    const dist = new Map([[start, 0]]);
    let frontier = [start];
    for (let d = 1; d <= depth; d++) {
      const next = [];
      for (const n of frontier) {
        const t = tables[n];
        const adj = t.relations.map((r) => r.ref_table).concat(t.referenced_by.map((r) => r.table));
        for (const m of adj) if (tables[m] && !dist.has(m)) { dist.set(m, d); next.push(m); }
      }
      frontier = next;
    }
    return dist;
  }
  function buildElements(tables, deg, set, groupOf) {
    const nodes = [], edges = [];
    for (const n of set) {
      const g = groupOf.get(n);
      nodes.push({ data: { id: n, label: n, deg: deg[n], hue: g == null ? -1 : (g * 47) % 360 } });
    }
    for (const n of set) {
      tables[n].relations.forEach((r, i) => {
        if (!set.has(r.ref_table)) return;
        edges.push({ classes: r.inferred ? 'inferred' : '', data: { id: n + '\u0001' + i, source: n, target: r.ref_table,
          col: r.col + (r.ref_col ? ' → ' + r.ref_col : '') + (r.inferred ? ' (probable)' : '') } });
      });
    }
    return nodes.concat(edges);
  }

  /* ---------------- estilo (sensible al tema) ---------------- */
  function stylesheet() {
    const text = cssVar('--text'), panel = cssVar('--panel'), border = cssVar('--border-2'), accent = cssVar('--accent'),
      faint = cssVar('--faint'), mapbg = cssVar('--map-bg');
    const light = isLight();
    const tone = (e) => { const hu = e.data('hue'); return hu < 0 ? faint : 'hsl(' + hu + ',' + (light ? 62 : 68) + '%,' + (light ? 42 : 64) + '%)'; };
    return [
      { selector: 'node', style: {
        shape: 'round-rectangle', label: 'data(label)', 'font-family': cssVar('--mono') || 'monospace', 'font-size': 11, color: text,
        'text-valign': 'center', 'text-halign': 'center', width: 'label', height: 'label', padding: '9px',
        'text-max-width': '190px', 'text-wrap': 'ellipsis', 'background-color': panel,
        'border-width': (e) => 1.2 + Math.min(3, e.data('deg') / 5), 'border-color': tone, 'min-zoomed-font-size': 6,
        'transition-property': 'opacity', 'transition-duration': '120ms' } },
      { selector: 'node.center', style: { 'border-width': 4, 'border-color': accent, 'font-weight': 'bold' } },
      { selector: 'node:selected', style: { 'border-width': 4, 'border-color': accent, 'underlay-color': accent, 'underlay-opacity': 0.25, 'underlay-padding': 6 } },
      { selector: 'node.found', style: { 'underlay-color': accent, 'underlay-opacity': 0.4, 'underlay-padding': 7 } },
      { selector: 'edge', style: {
        width: 1.4, 'line-color': border, 'curve-style': 'bezier', 'control-point-step-size': 38, 'target-arrow-shape': 'triangle',
        'target-arrow-color': border, 'arrow-scale': 0.9, opacity: 0.9 } },
      { selector: 'edge.inferred', style: { 'line-style': 'dashed', 'line-dash-pattern': [6, 5], 'line-color': cssVar('--warn'), 'target-arrow-color': cssVar('--warn'),
        'target-arrow-shape': 'vee', opacity: 0.75 } },
      { selector: '.faded', style: { opacity: 0.08, 'text-opacity': 0.1 } },
      { selector: 'edge.hl', style: {
        'line-color': accent, 'target-arrow-color': accent, width: 2.6, opacity: 1, label: 'data(col)', 'font-size': 10, color: accent,
        'font-family': cssVar('--mono') || 'monospace', 'text-background-color': mapbg, 'text-background-opacity': 1, 'text-background-padding': 3,
        'text-rotation': 'autorotate', 'z-index': 20 } },
      { selector: 'node.hl', style: { opacity: 1 } },
    ];
  }

  /* ---------------- posiciones ---------------- */
  function savedPositions() { const m = Etch.state.schema.map || {}; return m.positions || {}; }
  const persist = debounce(() => {
    if (!cy || ui.scope === 'focus') return;
    const positions = Object.assign({}, savedPositions());
    cy.nodes().forEach((n) => { const p = n.position(); positions[n.id()] = { x: Math.round(p.x * 10) / 10, y: Math.round(p.y * 10) / 10 }; });
    const state = { positions, layout: ui.layout };
    Etch.state.schema.map = state;
    Etch.api.save_map_state(Etch.state.alias, state);
  }, 450);

  function layoutOptions(kind, fixed, center, dist) {
    const base = { animate: false, fit: false, padding: 40 };
    switch (kind) {
      case 'breadthfirst':
        return Object.assign(base, { name: 'breadthfirst', directed: false, spacingFactor: 1.15,
          roots: cy.nodes().filter((n) => n.outgoers('edge').length === 0) });
      case 'concentric':
        return Object.assign(base, { name: 'concentric', concentric: (n) => (dist ? 10 - (dist.get(n.id()) || 0) : n.data('deg')), levelWidth: () => 1, minNodeSpacing: 46 });
      case 'circle': return Object.assign(base, { name: 'circle', spacingFactor: 1.2 });
      case 'grid': return Object.assign(base, { name: 'grid', spacingFactor: 1.15, avoidOverlap: true });
      default: {
        const o = Object.assign(base, { name: fcoseReady && window.cytoscapeFcose ? 'fcose' : 'cose', quality: 'default', randomize: !fixed,
          nodeDimensionsIncludeLabels: true, packComponents: true, tile: false, idealEdgeLength: 150, nodeRepulsion: 14000,
          edgeElasticity: 0.45, gravity: 0.3, gravityRange: 3.8, numIter: 2500, nodeSeparation: 90 });
        if (fixed && fixed.length) o.fixedNodeConstraint = fixed;
        return o;
      }
    }
  }

  function gridPlace(nodes, top) {
    if (!nodes.length) return;
    const cols = Math.max(4, Math.ceil(Math.sqrt(nodes.length * 2.4)));
    const dx = 200, dy = 52;
    const left = cy.nodes().not(nodes).length ? cy.nodes().not(nodes).boundingBox().x1 : 0;
    nodes.forEach((n, i) => n.position({ x: left + (i % cols) * dx + 90, y: top + Math.floor(i / cols) * dy }));
  }

  /* Coloca los nodos: restaura lo guardado y solo calcula layout para lo que falta. */
  function place(forceFresh) {
    const saved = forceFresh ? {} : savedPositions();
    const useSaved = ui.scope !== 'focus';
    const has = (n) => useSaved && saved[n.id()];
    const nodes = cy.nodes();
    nodes.forEach((n) => { if (has(n)) n.position({ x: saved[n.id()].x, y: saved[n.id()].y }); });

    const related = nodes.filter((n) => n.data('deg') > 0), orph = nodes.filter((n) => n.data('deg') === 0);
    const missing = related.filter((n) => !has(n));
    const dist = ui.scope === 'focus' ? neighborhood(view.tables, ui.focus, ui.depth) : null;

    if (related.length && missing.length) {
      let kind = ui.layout;
      if (ui.scope === 'focus' && kind === 'fcose') kind = 'concentric';
      const partial = kind === 'fcose' && missing.length < related.length;
      const fixed = partial ? related.filter(has).map((n) => ({ nodeId: n.id(), position: { x: saved[n.id()].x, y: saved[n.id()].y } })) : null;
      // Las aristas deben ir en la colección: un layout sobre nodos sueltos las ignoraría.
      related.union(related.connectedEdges()).layout(layoutOptions(kind, fixed, ui.focus, dist)).run();
    }
    const orphMissing = orph.filter((n) => !has(n));
    if (orphMissing.length) {
      const placed = nodes.not(orphMissing);
      const bottom = placed.length ? placed.boundingBox().y2 + 110 : 0;
      gridPlace(orphMissing, bottom);
    }
    cy.fit(undefined, 50);
  }

  /* ---------------- foco al pasar el mouse ---------------- */
  function applyFocus(n) {
    const nb = n.closedNeighborhood();
    cy.elements().not(nb).addClass('faded');
    nb.removeClass('faded');
    nb.edges().addClass('hl');
  }
  function clearFocus() {
    cy.elements().removeClass('faded hl');
    const sel = ui.selected && cy.getElementById(ui.selected);
    if (sel && sel.nonempty()) applyFocus(sel);
  }

  /* ---------------- vista ---------------- */
  Etch.views.map = {
    render(root, args) {
      const S = Etch.state, inferredAll = S.schema.inferred || [];
      const showInferred = !!S.settings.map_show_inferred && inferredAll.length > 0;
      const tables = showInferred ? withInferred(S.schema.tables, inferredAll) : S.schema.tables;
      view.tables = tables;
      const names = Object.keys(tables);
      if (!window.cytoscape) { root.append(h('div', { class: 'page' }, h('div', { class: 'card' }, h('h2', null, 'No se pudo cargar el motor del mapa'), h('p', { class: 'muted' }, 'Falta vendor/cytoscape.min.js.')))); return; }
      ensureFcose();

      const deg = degreeMap(tables);
      const relatedCount = names.filter((n) => deg[n] > 0).length;
      const comps = Etch.schemaComponents(tables);
      const groupOf = new Map();
      comps.forEach((c, i) => c.forEach((n) => groupOf.set(n, i)));
      const hubs = names.filter((n) => deg[n] > 0).sort((a, b) => deg[b] - deg[a]);

      if (ui.alias !== S.alias) Object.assign(ui, { alias: S.alias, scope: null, focus: null, selected: null, depth: 2 });
      ui.layout = ui.layout || S.settings.map_layout || 'fcose';
      if (args.focus && tables[args.focus]) { ui.scope = 'focus'; ui.focus = args.focus; ui.selected = args.focus; }
      if (!ui.scope) ui.scope = S.settings.map_include_orphans ? 'all' : 'related';
      if (ui.scope === 'focus' && (!ui.focus || !tables[ui.focus])) ui.focus = hubs[0] || names[0];
      if (ui.scope === 'related' && !relatedCount) ui.scope = 'all';

      /* ---- barra de herramientas ---- */
      const scopeSel = h('select', { class: 'select', 'aria-label': 'Alcance del mapa' },
        h('option', { value: 'related' }, 'Tablas con relaciones (' + relatedCount + ')'),
        h('option', { value: 'all' }, 'Todas las tablas (' + names.length + ')'),
        h('option', { value: 'focus' }, 'Vecindad de una tabla…'));
      scopeSel.value = ui.scope;
      const focusSel = h('select', { class: 'select', 'aria-label': 'Tabla central', style: { maxWidth: '220px' } },
        (hubs.length ? hubs : names).map((n) => h('option', { value: n }, n)));
      const depthSel = h('select', { class: 'select', 'aria-label': 'Profundidad', style: { minWidth: '110px' } },
        [1, 2, 3].map((d) => h('option', { value: String(d) }, 'Profundidad ' + d)));
      const layoutSel = h('select', { class: 'select', 'aria-label': 'Tipo de layout' }, LAYOUTS.map(([v, l]) => h('option', { value: v }, l)));
      layoutSel.value = ui.layout;
      const search = h('input', { class: 'input', type: 'search', placeholder: 'Buscar tabla en el mapa…', autocomplete: 'off', 'aria-label': 'Buscar tabla en el mapa' });
      const stats = h('span', { class: 'faint', style: { fontSize: '12px' } });
      const focusGroup = h('div', { class: 'row' }, focusSel, depthSel);
      const body = h('div', { class: 'map-body' });
      const container = h('div', { id: 'cy' });
      const overlay = h('div', { class: 'map-overlay map-empty', hidden: true });
      const legend = h('div', { class: 'map-overlay map-legend' },
        h('span', null, h('i'), 'FK → tabla referenciada'),
        showInferred ? h('span', null, h('i', { class: 'dash' }), 'Relación probable (por nombre)') : null,
        h('span', null, 'Color = grupo de tablas conectadas'), h('span', null, 'Pasá el mouse para enfocar · arrastrá para ordenar'));
      body.append(container, overlay, legend);
      let panel = null;

      const infBtn = h('button', { class: 'chip', 'aria-pressed': String(showInferred), disabled: !inferredAll.length,
        title: inferredAll.length ? 'Muestra relaciones que la base no declara pero que los nombres sugieren (línea punteada). Son sugerencias, no claves foráneas reales.' : 'No se encontraron relaciones probables por nombre en este esquema.',
        onclick: async () => { await Etch.saveSetting('map_show_inferred', !showInferred); Etch.render(); } },
        icon('zap', 13), 'Probables (' + inferredAll.length + ')');
      const btn = (ico, title, fn, label) => h('button', { class: 'btn sm' + (label ? '' : ' icon-only'), title, 'aria-label': title, onclick: fn }, icon(ico, 15), label || null);
      const tools = h('div', { class: 'map-tools' },
        scopeSel, focusGroup, h('span', { class: 'sep' }), layoutSel, infBtn, h('span', { class: 'sep' }),
        h('div', { class: 'searchbox' }, icon('search', 15), search), stats, h('div', { class: 'grow' }),
        btn('fit', 'Ajustar a la pantalla', () => cy && cy.animate({ fit: { padding: 50 } }, { duration: 250 })),
        btn('minus', 'Alejar', () => zoomBy(1 / 1.3)), btn('plus', 'Acercar', () => zoomBy(1.3)),
        btn('zap', 'Reorganizar automáticamente (descarta las posiciones guardadas de esta vista)', () => draw(true), 'Auto-organizar'),
        btn('download', 'Exportar como imagen PNG', exportPng, 'PNG'));
      root.append(h('div', { class: 'map-view' }, tools, body));

      function zoomBy(f) { if (!cy) return; cy.animate({ zoom: { level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } } }, { duration: 160 }); }

      function syncTools() {
        focusGroup.hidden = ui.scope !== 'focus';
        if (ui.focus) focusSel.value = ui.focus;
        depthSel.value = String(ui.depth);
        scopeSel.value = ui.scope;
      }

      /* ---- dibujo ---- */
      function visibleSet() {
        if (ui.scope === 'focus') return new Set(neighborhood(tables, ui.focus, ui.depth).keys());
        return new Set(names.filter((n) => ui.scope === 'all' || deg[n] > 0));
      }
      function draw(fresh) {
        if (cy) { cy.destroy(); cy = null; }
        closePanel(true);
        const set = visibleSet();
        const els = buildElements(tables, deg, set, groupOf);
        cy = window.cytoscape({ container, elements: els, style: stylesheet(), minZoom: 0.04, maxZoom: 3, wheelSensitivity: 0.25,
          textureOnViewport: set.size > 400, hideEdgesOnViewport: set.size > 600, boxSelectionEnabled: false });
        window.__cy = cy; // útil para depurar desde la consola del navegador
        if (ui.scope === 'focus') cy.getElementById(ui.focus).addClass('center');
        syncTools();

        overlay.hidden = set.size > 0;
        if (!set.size) {
          clear(overlay).append(h('div', null, icon('map', 36), h('h2', { style: { color: 'var(--text)' } }, 'No hay nada para mostrar'),
            h('div', null, 'Esta base no declara relaciones entre tablas.'), h('button', { class: 'btn', style: { marginTop: '12px', pointerEvents: 'auto' }, onclick: () => { ui.scope = 'all'; draw(); } }, 'Mostrar todas las tablas')));
        }
        const relEdges = cy.edges().length;
        stats.textContent = Etch.plural(cy.nodes().length, 'tabla', 'tablas') + ' · ' + Etch.plural(relEdges, 'relación', 'relaciones') + (cy.edges('.inferred').length ? ' (' + cy.edges('.inferred').length + ' probables)' : '');
        if (!set.size) return;

        const saved = savedPositions();
        const needsSave = !!fresh || cy.nodes().some((n) => !saved[n.id()]);
        place(!!fresh);
        if (needsSave) persist();

        cy.on('mouseover', 'node', (e) => { if (!e.target.grabbed()) applyFocus(e.target); });
        cy.on('mouseout', 'node', clearFocus);
        cy.on('grab', 'node', () => { container.style.cursor = 'grabbing'; });
        cy.on('free', 'node', () => { container.style.cursor = ''; });
        cy.on('dragfree', 'node', persist);
        cy.on('tap', 'node', (e) => openPanel(e.target.id()));
        cy.on('dbltap', 'node', (e) => { ui.scope = 'focus'; ui.focus = e.target.id(); draw(); openPanel(ui.focus); });
        cy.on('tap', (e) => { if (e.target === cy) closePanel(); });
        if (ui.selected && cy.getElementById(ui.selected).nonempty()) openPanel(ui.selected, true);
      }

      /* ---- panel lateral ---- */
      function closePanel(silent) {
        if (panel) { panel.remove(); panel = null; }
        ui.selected = null;
        if (cy && !silent) { cy.nodes().unselect(); clearFocus(); }
      }
      function openPanel(name, noCenter) {
        const t = tables[name];
        if (!t) return;
        if (panel) panel.remove();
        ui.selected = name;
        cy.nodes().unselect();
        const node = cy.getElementById(name);
        node.select();
        applyFocus(node);
        if (!noCenter) {
          const p = node.renderedPosition();
          if (p.x > cy.width() - 380 || p.x < 0 || p.y < 0 || p.y > cy.height()) cy.animate({ center: { eles: node } }, { duration: 250 });
        }
        const go = (n) => { if (cy.getElementById(n).nonempty()) openPanel(n); else Etch.openTable(n); };
        const link = (n, extra) => h('button', { class: 'linkbtn', onclick: () => go(n), title: 'Ir a ' + n }, n, extra || null);
        panel = h('aside', { class: 'map-panel', 'aria-label': 'Detalle de la tabla' },
          h('header', null, h('div', { class: 'grow' }, h('b', { class: 'mono' }, name),
            h('div', { class: 'muted', style: { fontSize: '12px', marginTop: '2px' } }, Etch.plural(t.columns.length, 'columna', 'columnas') + ' · ' + Etch.plural(deg[name], 'relación', 'relaciones'))),
            h('button', { class: 'btn icon-only ghost', 'aria-label': 'Cerrar panel', onclick: () => closePanel() }, icon('x', 16))),
          h('div', { class: 'body' },
            h('div', { class: 'sec-title', style: { marginTop: '4px' } }, 'Columnas'),
            t.columns.slice(0, 80).map((c) => h('div', { class: 'mini-col' },
              c.pk ? h('span', { class: 'badge pk' }, 'PK') : c.fk ? h('span', { class: 'badge fk' }, 'FK') : h('span', { style: { width: '30px' } }),
              h('span', { class: 'nm truncate' }, c.name), h('span', { class: 'ty truncate' }, c.type))),
            t.columns.length > 80 ? h('div', { class: 'faint', style: { fontSize: '12px', padding: '4px 6px' } }, '… y ' + (t.columns.length - 80) + ' más en el Explorador') : null,
            t.relations.length ? h('div', { class: 'sec-title' }, 'Referencia a') : null,
            t.relations.map((r) => h('div', { class: 'mini-col' }, h('span', { class: 'mono faint' }, r.col), icon('arrow', 13), link(r.ref_table),
              r.inferred ? h('span', { class: 'badge warn', title: r.reason || 'Relación probable' }, 'prob.') : null)),
            t.referenced_by.length ? h('div', { class: 'sec-title' }, 'Referenciada por') : null,
            t.referenced_by.slice(0, 60).map((r) => h('div', { class: 'mini-col' }, link(r.table), h('span', { class: 'mono faint' }, '.' + r.col),
              r.inferred ? h('span', { class: 'badge warn', title: 'Relación probable (por nombre)' }, 'prob.') : null))),
          h('div', { class: 'foot2' },
            h('button', { class: 'btn sm primary', onclick: () => Etch.openTable(name) }, icon('table', 14), 'Abrir en el Explorador'),
            ui.scope === 'focus' && ui.focus === name ? null :
              h('button', { class: 'btn sm', onclick: () => { ui.scope = 'focus'; ui.focus = name; draw(); openPanel(name, true); } }, icon('target', 14), 'Enfocar vecindad')));
        body.append(panel);
      }

      /* ---- eventos de la barra ---- */
      scopeSel.addEventListener('change', () => {
        ui.scope = scopeSel.value;
        if (ui.scope === 'focus' && !ui.focus) ui.focus = ui.selected || hubs[0] || names[0];
        if (ui.scope !== 'focus') Etch.saveSetting('map_include_orphans', ui.scope === 'all');
        draw();
      });
      focusSel.addEventListener('change', () => { ui.focus = focusSel.value; draw(); });
      depthSel.addEventListener('change', () => { ui.depth = Number(depthSel.value); draw(); });
      layoutSel.addEventListener('change', () => {
        ui.layout = layoutSel.value;
        Etch.saveSetting('map_layout', ui.layout);
        draw(true);
      });
      const doFind = debounce(() => {
        if (!cy) return;
        const q = search.value.trim().toLowerCase();
        cy.nodes().removeClass('found');
        if (!q) return;
        cy.nodes().filter((n) => n.id().toLowerCase().includes(q)).addClass('found');
      }, 100);
      search.addEventListener('input', doFind);
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { search.value = ''; doFind(); search.blur(); }
        if (e.key === 'Enter' && cy) {
          const hit = cy.nodes('.found').first();
          if (hit.nonempty()) { cy.animate({ center: { eles: hit }, zoom: Math.max(cy.zoom(), 1) }, { duration: 300 }); openPanel(hit.id(), true); }
        }
      });

      async function exportPng() {
        if (!cy || !cy.nodes().length) return;
        const bb = cy.elements().boundingBox();
        const scale = Math.max(0.2, Math.min(2, 7000 / Math.max(bb.w, bb.h, 1)));
        const uri = cy.png({ output: 'base64uri', full: true, scale, bg: cssVar('--map-bg') || '#0a0f1a' });
        const r = await Etch.api.save_file(S.alias.replace(/[^\w.-]+/g, '_') + '_mapa.png', uri.split(',')[1], 'base64');
        if (r.ok) Etch.toast('success', 'Mapa exportado', { detail: r.path });
        else if (!r.cancelled) Etch.toast('error', 'No se pudo exportar el mapa', { detail: r.error });
      }

      onResize = () => { if (cy) cy.resize(); };
      if (window.ResizeObserver) { ro = new ResizeObserver(onResize); ro.observe(body); }
      else window.addEventListener('resize', onResize);

      draw();
    },

    onTheme() { if (cy) { cy.style(stylesheet()); } },

    destroy() {
      if (ro) { ro.disconnect(); ro = null; }
      if (onResize) { window.removeEventListener('resize', onResize); onResize = null; }
      if (cy) { cy.destroy(); cy = null; }
      window.__cy = null;
    },
  };
})();
