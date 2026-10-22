/* Utilidades compartidas. Todo cuelga de window.Etch (sin módulos ES: la app se
   sirve desde file:// y Chromium bloquea los <script type="module"> locales). */
(function () {
  'use strict';
  const Etch = (window.Etch = window.Etch || {});
  Etch.dialogs = {};
  Etch.views = {};

  /* ---------------- íconos (trazos estilo "feather", 24x24) ---------------- */
  const ICONS = {
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 11v6M14 11v6"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/>',
    link: '<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
    map: '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 10.5l6.8-4M8.6 13.5l6.8 4"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7"/><path d="M12 17h.01"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>',
    monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    x: '<path d="M18 6L6 18M6 6l12 12"/>',
    check: '<path d="M20 6L9 17l-5-5"/>',
    alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeoff: '<path d="M3 3l18 18"/><path d="M10.6 6.1A9.8 9.8 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 4M6.5 6.7A17 17 0 0 0 2 12s4 7 10 7a9.6 9.6 0 0 0 4.3-1"/>',
    download: '<path d="M12 4v11M7 11l5 5 5-5"/><path d="M4 20h16"/>',
    fit: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    play: '<path d="M7 4l13 8-13 8z"/>',
    sidebar: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    grid: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>',
    minus: '<path d="M5 12h14"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    route: '<circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="5" r="2.2"/><path d="M8 19h6.5a3.5 3.5 0 0 0 0-7h-5a3.5 3.5 0 0 1 0-7H16"/>',
    migrate: '<path d="M4 8h13l-3-3"/><path d="M20 16H7l3 3"/>',
    dots: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
  };

  function icon(name, size) {
    const span = document.createElement('span');
    span.className = 'icon';
    const s = (size || 16) + 'px';
    span.style.width = s; span.style.height = s;
    span.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[name] || '') + '</svg>'; // trusted constant
    return span;
  }

  /* ---------------- DOM ---------------- */
  function append(el, children) {
    for (const c of children.flat(Infinity)) {
      if (c == null || c === false) continue;
      el.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
  }
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === 'class') el.className = v;
        else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
        else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
        else el.setAttribute(k, v === true ? '' : v);
      }
    }
    append(el, children);
    return el;
  }
  const $ = (sel, root) => (root || document).querySelector(sel);
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* ---------------- formato ---------------- */
  const nf = new Intl.NumberFormat('es');
  function num(n) { return nf.format(n || 0); }
  function plural(n, one, many) { return num(n) + ' ' + (n === 1 ? one : many); }
  function parseDate(str) { return str ? new Date(String(str).replace(' ', 'T')) : null; }
  function relTime(str) {
    const d = parseDate(str);
    if (!d || isNaN(d)) return 'nunca';
    const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (s < 45) return 'hace un instante';
    if (s < 3600) return 'hace ' + Math.round(s / 60) + ' min';
    if (s < 86400) return 'hace ' + Math.round(s / 3600) + ' h';
    if (s < 86400 * 30) return 'hace ' + Math.round(s / 86400) + ' d';
    return d.toLocaleDateString('es');
  }
  function fmtDate(str) {
    const d = parseDate(str);
    return d && !isNaN(d) ? d.toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
  }
  function fmtDuration(sec) {
    if (sec == null) return '—';
    return sec < 60 ? sec.toFixed(sec < 10 ? 2 : 1) + ' s' : Math.floor(sec / 60) + ' min ' + Math.round(sec % 60) + ' s';
  }
  const ENGINES = {
    postgres: { label: 'PostgreSQL', short: 'PG' }, mssql: { label: 'SQL Server', short: 'MSSQL' },
    mysql: { label: 'MySQL', short: 'MySQL' }, sqlite: { label: 'SQLite', short: 'SQLite' },
    oracle: { label: 'Oracle', short: 'ORA' }, firebird: { label: 'Firebird', short: 'FB' },
    db2: { label: 'DB2', short: 'DB2' }, mongodb: { label: 'MongoDB', short: 'Mongo' },
  };
  const engineLabel = (e) => (ENGINES[e] ? ENGINES[e].label : e || 'Desconocido');
  const engineShort = (e) => (ENGINES[e] ? ENGINES[e].short : (e || '?').toUpperCase());

  /* ---------------- portapapeles ---------------- */
  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* cae al método clásico */ }
    const ta = h('textarea', { style: { position: 'fixed', opacity: '0', top: '0' } });
    ta.value = text; document.body.append(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }

  /* ---------------- DDL aproximado ---------------- */
  function quoteIdent(engine, name) {
    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) return name;
    if (engine === 'mssql') return '[' + name.replace(/]/g, ']]') + ']';
    if (engine === 'mysql') return '`' + name.replace(/`/g, '``') + '`';
    return '"' + name.replace(/"/g, '""') + '"';
  }
  function buildDDL(engine, key, info) {
    const q = (n) => quoteIdent(engine, n);
    const lines = info.columns.map((c) => '  ' + q(c.name) + ' ' + (c.type || 'text') + (c.null ? '' : ' NOT NULL'));
    const pks = info.columns.filter((c) => c.pk).map((c) => q(c.name));
    if (pks.length) lines.push('  PRIMARY KEY (' + pks.join(', ') + ')');
    for (const r of info.relations) {
      lines.push('  FOREIGN KEY (' + q(r.col) + ') REFERENCES ' + q(r.ref_table) + (r.ref_col ? ' (' + q(r.ref_col) + ')' : ''));
    }
    return '-- DDL aproximado generado por Etch-DB-Mapper a partir del esquema leído\n' +
           'CREATE TABLE ' + q(key) + ' (\n' + lines.join(',\n') + '\n);';
  }

  /* ---------------- resaltado de búsqueda ---------------- */
  function highlight(text, query) {
    const frag = document.createDocumentFragment();
    const q = (query || '').trim().toLowerCase();
    const i = q ? text.toLowerCase().indexOf(q) : -1;
    if (i < 0) { frag.append(text); return frag; }
    frag.append(text.slice(0, i), h('mark', null, text.slice(i, i + q.length)), text.slice(i + q.length));
    return frag;
  }

  /* ---------------- Markdown mínimo (para HELP.md / CHANGELOG.md) ---------------- */
  function inline(src) {
    let s = escapeHtml(src);
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (m, c) => { codes.push(c); return '\u0000' + (codes.length - 1) + '\u0000'; });
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
         .replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>')
         .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|#[^)\s]*)\)/g, '<a href="$2">$1</a>');
    return s.replace(/\u0000(\d+)\u0000/g, (m, i) => '<code>' + codes[i] + '</code>');
  }
  function parseList(lines, i) {
    const base = lines[i].match(/^\s*/)[0].length;
    const ordered = /^\s*\d+\./.test(lines[i]);
    const items = [];
    while (i < lines.length) {
      const ln = lines[i];
      const m = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(ln);
      if (!m) {
        if (ln.trim() !== '' && /^\s{2,}\S/.test(ln) && items.length) { items[items.length - 1].text += ' ' + ln.trim(); i++; continue; }
        break;
      }
      const indent = m[1].length;
      if (indent < base) break;
      if (indent > base && items.length) {
        const [sub, ni] = parseList(lines, i);
        items[items.length - 1].sub += sub; i = ni; continue;
      }
      items.push({ text: m[3], sub: '' }); i++;
    }
    const tag = ordered ? 'ol' : 'ul';
    return ['<' + tag + '>' + items.map((it) => '<li>' + inline(it.text) + it.sub + '</li>').join('') + '</' + tag + '>', i];
  }
  const slug = (t) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  function renderMarkdown(md) {
    const lines = String(md).replace(/\r\n/g, '\n').split('\n');
    const out = [], heads = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      let m;
      if (/^```/.test(line)) {
        const buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
        i++; out.push('<pre><code>' + escapeHtml(buf.join('\n')) + '</code></pre>'); continue;
      }
      if ((m = /^(#{1,3})\s+(.*)$/.exec(line))) {
        const level = m[1].length, text = m[2].trim(), id = slug(text.replace(/`/g, ''));
        if (level === 2) heads.push({ id, text: text.replace(/`/g, '') });
        out.push('<h' + level + ' id="' + id + '">' + inline(text) + '</h' + level + '>'); i++; continue;
      }
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
      if (/^>\s?/.test(line)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''));
        out.push('<blockquote>' + inline(buf.join(' ')) + '</blockquote>'); continue;
      }
      if (/^\s*([-*]|\d+\.)\s+/.test(line)) { const [html, ni] = parseList(lines, i); out.push(html); i = ni; continue; }
      if (line.includes('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(lines[i + 1])) {
        const cells = (l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
        const head = cells(line); i += 2;
        const rows = [];
        while (i < lines.length && lines[i].includes('|')) rows.push(cells(lines[i++]));
        out.push('<table><thead><tr>' + head.map((c) => '<th>' + inline(c) + '</th>').join('') + '</tr></thead><tbody>' +
          rows.map((r) => '<tr>' + r.map((c) => '<td>' + inline(c) + '</td>').join('') + '</tr>').join('') + '</tbody></table>');
        continue;
      }
      if (line.trim() === '') { i++; continue; }
      const buf = [];
      while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,3}\s|```|>\s?|\s*([-*]|\d+\.)\s+|\s*(-{3,}|\*{3,})\s*$)/.test(lines[i])) buf.push(lines[i++].trim());
      out.push('<p>' + inline(buf.join(' ')) + '</p>');
    }
    return { html: out.join('\n'), headings: heads };
  }

  Object.assign(Etch, {
    icon, h, $, clear, debounce, escapeHtml, num, plural, relTime, fmtDate, fmtDuration,
    engineLabel, engineShort, copyText, quoteIdent, buildDDL, highlight, renderMarkdown, parseDate,
  });
})();
