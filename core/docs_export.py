"""Exportar el diccionario de datos: Markdown, CSV (se abre en Excel) e informe HTML
interactivo de un solo archivo (con el mapa), listo para compartir sin instalar la app.

Qué incluye: nombres de tablas y columnas, tipos, claves, relaciones, las descripciones
que la base ya tenía y las notas del usuario. **Nunca** datos de las tablas, URI ni
contraseñas.

Todo texto que viene de la base o del usuario se escapa (HTML) o se serializa como JSON
inerte: un nombre de tabla con `<script>` no puede ejecutar nada en el informe.
"""
import csv
import html
import io
import json
import re
from datetime import datetime

from .paths import resource_path
from .version import REPO_URL, __version__

VENDOR_FILES = ("cytoscape.min.js", "layout-base.js", "cose-base.js", "cytoscape-fcose.js")


def safe_filename(text: str, ext: str) -> str:
    base = re.sub(r"[^\w.\- ]+", "_", text or "esquema").strip(" ._") or "esquema"
    return f"{base}.{ext}"


def _tags(ann_entry: dict) -> list:
    return list(ann_entry.get("tags") or [])


def collect(tables: dict, inferred: list, annotations: dict) -> list:
    """Una ficha por tabla con la descripción combinada (nota del usuario > comentario de la base)."""
    ann = (annotations or {}).get("tables", {})
    out_inf, in_inf = {}, {}
    for r in inferred or []:
        out_inf.setdefault(r["table"], []).append(r)
        in_inf.setdefault(r["ref_table"], []).append(r)
    cards = []
    for name in sorted(tables, key=str.lower):
        t = tables[name]
        a = ann.get(name, {})
        col_notes = a.get("columns", {})
        fk = {r["col"]: r for r in t["relations"]}
        cols = []
        for c in t["columns"]:
            note = col_notes.get(c["name"], "")
            ref = fk.get(c["name"])
            cols.append({
                "name": c["name"], "type": c.get("type", ""), "null": bool(c.get("null")), "pk": bool(c.get("pk")),
                "fk": bool(c.get("fk")), "ref": (f"{ref['ref_table']}.{ref['ref_col']}" if ref else ""),
                "native": c.get("comment", "") or "", "note": note, "description": note or c.get("comment", "") or "",
            })
        cards.append({
            "name": name, "schema": t.get("schema", ""), "native": t.get("comment", "") or "", "note": a.get("note", ""),
            "description": a.get("note") or t.get("comment") or "", "owner": a.get("owner", ""), "tags": _tags(a),
            "columns": cols,
            "relations": [{"col": r["col"], "ref_table": r["ref_table"], "ref_col": r["ref_col"]} for r in t["relations"]],
            "referenced_by": [{"table": r["table"], "col": r["col"], "ref_col": r["ref_col"]} for r in t["referenced_by"]],
            "inferred_out": [{"col": r["col"], "ref_table": r["ref_table"], "ref_col": r["ref_col"], "confidence": r["confidence"]} for r in out_inf.get(name, [])],
            "inferred_in": [{"table": r["table"], "col": r["col"], "ref_col": r["ref_col"], "confidence": r["confidence"]} for r in in_inf.get(name, [])],
        })
    return cards


def coverage(cards: list) -> dict:
    documented = sum(1 for c in cards if c["description"])
    cols = sum(len(c["columns"]) for c in cards)
    cols_doc = sum(1 for c in cards for col in c["columns"] if col["description"])
    return {"tables": len(cards), "tables_documented": documented, "columns": cols, "columns_documented": cols_doc}


# ------------------------------------------------------------------ Markdown
def _md(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\r", "").replace("\n", " ")


def export_markdown(alias, engine, cards, last_scan) -> str:
    cov = coverage(cards)
    L = [f"# Diccionario de datos — {alias}", "",
         f"> Generado por Etch-DB-Mapper v{__version__} · motor: {engine or 'desconocido'} · último escaneo: {last_scan or '—'}", "",
         f"**{cov['tables']}** tablas · **{cov['columns']}** columnas · documentadas: {cov['tables_documented']} tablas y {cov['columns_documented']} columnas.", "",
         "## Índice", ""]
    for c in cards:
        L.append(f"- [`{c['name']}`](#{re.sub(r'[^a-z0-9]+', '-', c['name'].lower()).strip('-')})" + (f" — {_md(c['description'])[:110]}" if c["description"] else ""))
    for c in cards:
        L += ["", f"## `{c['name']}`", ""]
        if c["description"]:
            L += [c["description"], ""]
        meta = []
        if c["schema"] and c["schema"] != "main":
            meta.append(f"**Esquema:** `{c['schema']}`")
        if c["owner"]:
            meta.append(f"**Responsable:** {c['owner']}")
        if c["tags"]:
            meta.append("**Etiquetas:** " + ", ".join(f"`{t}`" for t in c["tags"]))
        if meta:
            L += [" · ".join(meta), ""]
        L += ["| Columna | Tipo | Nulos | Clave | Referencia | Descripción |", "|---|---|---|---|---|---|"]
        for col in c["columns"]:
            key = "PK" if col["pk"] else ("FK" if col["fk"] else "")
            L.append(f"| `{col['name']}` | {_md(col['type'])} | {'sí' if col['null'] else 'no'} | {key} | {_md(col['ref'])} | {_md(col['description'])} |")
        if c["referenced_by"]:
            L += ["", "**Referenciada por:** " + ", ".join(f"`{r['table']}.{r['col']}`" for r in c["referenced_by"])]
        probable = [f"`{r['col']}` → `{r['ref_table']}.{r['ref_col']}`" for r in c["inferred_out"]] + \
                   [f"`{r['table']}.{r['col']}` → esta tabla" for r in c["inferred_in"]]
        if probable:
            L += ["", "**Relaciones probables (deducidas por nombre, no son claves foráneas):** " + "; ".join(probable)]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------- CSV
def export_csv(cards) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["esquema", "tabla", "descripcion_tabla", "responsable", "etiquetas", "columna", "tipo", "admite_nulos", "pk", "fk",
                "referencia", "descripcion_columna", "origen_descripcion"])
    for c in cards:
        for col in c["columns"]:
            origin = "nota" if col["note"] else ("base de datos" if col["native"] else "")
            w.writerow([c["schema"], c["name"], c["description"], c["owner"], "; ".join(c["tags"]), col["name"], col["type"],
                        "sí" if col["null"] else "no", "sí" if col["pk"] else "", "sí" if col["fk"] else "", col["ref"], col["description"], origin])
    return "\ufeff" + buf.getvalue()      # BOM: Excel abre bien los acentos


# ---------------------------------------------------------------------- HTML
_CSS = """
:root{--bg:#f4f7fc;--panel:#fff;--text:#0f1b33;--muted:#566887;--border:#dde4f0;--accent:#0284c7;--warn:#b45309;--good:#059669;--pk:#b7791f;--fk:#2563eb;--mapbg:#f8fafd}
@media (prefers-color-scheme:dark){:root{--bg:#0a0f1a;--panel:#111a2c;--text:#e8eefb;--muted:#94a5c2;--border:#22304d;--accent:#38bdf8;--warn:#fbbf24;--good:#34d399;--pk:#f5c542;--fk:#60a5fa;--mapbg:#070b14}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
header{padding:22px 28px;border-bottom:1px solid var(--border);background:var(--panel)}header h1{margin:0 0 4px;font-size:22px}header p{margin:0;color:var(--muted)}
.wrap{max-width:1180px;margin:0 auto;padding:20px 28px 60px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.stat{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:10px 16px}.stat b{display:block;font-size:22px}
#map{height:520px;border:1px solid var(--border);border-radius:14px;background:var(--mapbg);margin:12px 0;position:relative}#cy{position:absolute;inset:0}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}button,input[type=search]{font:inherit;color:inherit;background:var(--panel);border:1px solid var(--border);border-radius:9px;padding:6px 12px}
button{cursor:pointer}button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}input[type=search]{min-width:260px}
details.tbl{background:var(--panel);border:1px solid var(--border);border-radius:12px;margin:8px 0}details.tbl>summary{cursor:pointer;padding:10px 14px;font-weight:650;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
details.tbl .body{padding:0 14px 14px}.desc{color:var(--muted)}.badge{font-size:11px;border:1px solid var(--border);border-radius:6px;padding:1px 6px;color:var(--muted)}
.tag{background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent);border-color:transparent}
table{border-collapse:collapse;width:100%;margin:8px 0}th,td{border:1px solid var(--border);padding:5px 9px;text-align:left;vertical-align:top}th{background:color-mix(in srgb,var(--border) 40%,transparent);font-size:12px}
code,.mono{font-family:Consolas,"Cascadia Mono",monospace;font-size:12.5px}.pk{color:var(--pk);font-weight:700}.fk{color:var(--fk);font-weight:700}.prob{color:var(--warn)}
footer{margin-top:30px;color:var(--muted);font-size:12px}a{color:var(--accent)}details.tbl.flash{outline:2px solid var(--accent)}
"""

_JS = r"""
(function(){
  var data=JSON.parse(document.getElementById('etch-data').textContent);
  function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim();}
  if(typeof cytoscape==='undefined'){document.getElementById('map').style.display='none';return;}
  try{cytoscape.use(cytoscapeFcose);}catch(e){}
  var showInf=false,showOrph=false;
  var cy=cytoscape({container:document.getElementById('cy'),elements:[],minZoom:.05,maxZoom:3,wheelSensitivity:.25,
    style:[
      {selector:'node',style:{shape:'round-rectangle',label:'data(id)','font-size':11,color:css('--text'),'font-family':'Consolas,monospace','text-valign':'center','text-halign':'center',width:function(e){return Math.min(210,26+e.id().length*7.2);},height:28,'text-max-width':'190px','text-wrap':'ellipsis','background-color':css('--panel'),'border-width':1.5,'border-color':function(e){var h=e.data('hue');return h<0?css('--muted'):'hsl('+h+',65%,52%)';},'min-zoomed-font-size':6}},
      {selector:'edge',style:{width:1.4,'line-color':css('--border'),'curve-style':'bezier','control-point-step-size':38,'target-arrow-shape':'triangle','target-arrow-color':css('--border'),'arrow-scale':.9}},
      {selector:'edge.inf',style:{'line-style':'dashed','line-color':css('--warn'),'target-arrow-color':css('--warn'),'target-arrow-shape':'vee'}},
      {selector:'.faded',style:{opacity:.08}},
      {selector:'edge.hl',style:{'line-color':css('--accent'),'target-arrow-color':css('--accent'),width:2.6,label:'data(col)','font-size':10,color:css('--accent'),'text-background-color':css('--mapbg'),'text-background-opacity':1,'text-background-padding':3}}
    ]});
  function build(){
    cy.elements().remove();
    var edges=data.edges.filter(function(e){return showInf||!e.inf;}),rel={};
    edges.forEach(function(e){rel[e.s]=1;rel[e.t]=1;});
    var nodes=data.nodes.filter(function(n){return rel[n.id]||showOrph;});
    var els=nodes.map(function(n){return {data:{id:n.id,hue:rel[n.id]?n.hue:-1}};});
    edges.forEach(function(e,i){els.push({classes:e.inf?'inf':'',data:{id:'e'+i,source:e.s,target:e.t,col:e.col+(e.inf?' (probable)':'')}});});
    cy.add(els);
    var ok=nodes.length&&nodes.every(function(n){return data.positions[n.id];});
    if(ok){cy.nodes().forEach(function(n){var p=data.positions[n.id()];n.position({x:p.x,y:p.y});});cy.fit(undefined,40);}
    else{cy.layout({name:(typeof cytoscapeFcose!=='undefined')?'fcose':'cose',animate:false,randomize:true,nodeDimensionsIncludeLabels:false,packComponents:true,tile:false,idealEdgeLength:150,nodeRepulsion:14000,fit:true,padding:40}).run();}
  }
  cy.on('mouseover','node',function(e){var nb=e.target.closedNeighborhood();cy.elements().not(nb).addClass('faded');nb.edges().addClass('hl');});
  cy.on('mouseout','node',function(){cy.elements().removeClass('faded hl');});
  cy.on('tap','node',function(e){var i=data.index[e.target.id()],d=document.getElementById('t'+i);if(d){d.open=true;d.scrollIntoView({behavior:'smooth',block:'start'});d.classList.add('flash');setTimeout(function(){d.classList.remove('flash');},1600);}});
  function toggle(id,fn){var b=document.getElementById(id);b.addEventListener('click',function(){var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on);fn(on);build();});}
  toggle('btn-inf',function(on){showInf=on;});toggle('btn-orph',function(on){showOrph=on;});
  document.getElementById('btn-fit').addEventListener('click',function(){cy.fit(undefined,40);});
  document.getElementById('q').addEventListener('input',function(e){var q=e.target.value.toLowerCase();document.querySelectorAll('details.tbl').forEach(function(d){d.hidden=q&&d.textContent.toLowerCase().indexOf(q)<0;});});
  build();
})();
"""


def _h(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def _table_html(i: int, c: dict) -> str:
    rows = []
    for col in c["columns"]:
        key = '<span class="pk">PK</span>' if col["pk"] else ('<span class="fk">FK</span>' if col["fk"] else "")
        rows.append(f"<tr><td><code>{_h(col['name'])}</code></td><td>{_h(col['type'])}</td><td>{'sí' if col['null'] else 'no'}</td><td>{key}</td>"
                    f"<td class=\"mono\">{_h(col['ref'])}</td><td>{_h(col['description'])}</td></tr>")
    tags = "".join(f'<span class="badge tag">{_h(t)}</span> ' for t in c["tags"])
    meta = []
    if c["owner"]:
        meta.append(f"Responsable: <b>{_h(c['owner'])}</b>")
    extra = []
    if c["referenced_by"]:
        extra.append("<p><b>Referenciada por:</b> " + ", ".join(f"<code>{_h(r['table'])}.{_h(r['col'])}</code>" for r in c["referenced_by"]) + "</p>")
    probable = [f"<code>{_h(r['col'])}</code> → <code>{_h(r['ref_table'])}.{_h(r['ref_col'])}</code>" for r in c["inferred_out"]] + \
               [f"<code>{_h(r['table'])}.{_h(r['col'])}</code> → esta tabla" for r in c["inferred_in"]]
    if probable:
        extra.append('<p class="prob"><b>Relaciones probables</b> (deducidas por nombre, no son claves foráneas): ' + "; ".join(probable) + "</p>")
    desc = f'<span class="desc">{_h(c["description"][:140])}</span>' if c["description"] else ""
    return (f'<details class="tbl" id="t{i}"><summary><span class="mono">{_h(c["name"])}</span> {tags}{desc}</summary><div class="body">'
            + (f"<p>{_h(c['description'])}</p>" if c["description"] else "")
            + (f"<p>{' · '.join(meta)}</p>" if meta else "")
            + '<table><thead><tr><th>Columna</th><th>Tipo</th><th>Nulos</th><th>Clave</th><th>Referencia</th><th>Descripción</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>" + "".join(extra) + "</div></details>")


def _read_vendor() -> str:
    parts = []
    for name in VENDOR_FILES:
        text = resource_path("webui", "vendor", name).read_text(encoding="utf-8")
        parts.append(text.replace("</script", "<\\/script"))
    return "\n;\n".join(parts)


def export_html(alias, engine, cards, inferred, last_scan, positions=None, with_map=True) -> str:
    cov = coverage(cards)
    index = {c["name"]: i for i, c in enumerate(cards)}
    deg = {c["name"]: len(c["relations"]) + len(c["referenced_by"]) for c in cards}
    declared = [(c["name"], r["ref_table"], r["col"], False) for c in cards for r in c["relations"] if r["ref_table"] in index]
    probable = [(r["table"], r["ref_table"], r["col"], True) for r in inferred or [] if r["table"] in index and r["ref_table"] in index]
    # grupo (color) por componente conexa, igual que el mapa de la app
    parent = {n: n for n in index}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for s, t, _c, _i in declared + probable:
        parent[find(s)] = find(t)
    groups = {}
    for n in index:
        groups.setdefault(find(n), []).append(n)
    ordered = sorted((g for g in groups.values() if len(g) > 1), key=lambda g: -len(g))
    hue = {}
    for gi, g in enumerate(ordered):
        for n in g:
            hue[n] = (gi * 47) % 360
    data = {
        "index": index,
        "nodes": [{"id": n, "hue": hue.get(n, -1)} for n in index],
        "edges": [{"s": s, "t": t, "col": c, "inf": i} for s, t, c, i in declared + probable],
        "positions": {k: {"x": v["x"], "y": v["y"]} for k, v in (positions or {}).items() if k in index and isinstance(v, dict) and "x" in v and "y" in v},
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    map_block = ""
    scripts = ""
    if with_map:
        map_block = ('<h2>Mapa de relaciones</h2><div class="bar"><button id="btn-inf" aria-pressed="false" title="Líneas punteadas: deducidas por nombre">Relaciones probables</button>'
                     '<button id="btn-orph" aria-pressed="false">Tablas sin relaciones</button><button id="btn-fit">Ajustar</button>'
                     '<span class="desc">Pasa el mouse para enfocar · clic para ir a la tabla</span></div><div id="map"><div id="cy"></div></div>')
        scripts = f"<script>{_read_vendor()}</script><script>{_JS}</script>"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diccionario de datos — {_h(alias)}</title><style>{_CSS}</style></head><body>
<header><h1>Diccionario de datos — {_h(alias)}</h1>
<p>Motor: {_h(engine or 'desconocido')} · último escaneo: {_h(last_scan or '—')} · generado el {now} con Etch-DB-Mapper v{__version__}</p></header>
<div class="wrap">
<div class="stats"><div class="stat"><b>{cov['tables']}</b>tablas</div><div class="stat"><b>{cov['columns']}</b>columnas</div>
<div class="stat"><b>{len(declared)}</b>relaciones (FK)</div><div class="stat"><b>{len(probable)}</b>relaciones probables</div>
<div class="stat"><b>{cov['tables_documented']}/{cov['tables']}</b>tablas documentadas</div></div>
{map_block}
<h2>Tablas</h2><div class="bar"><input id="q" type="search" placeholder="Buscar tabla, columna o nota…" aria-label="Buscar"></div>
{''.join(_table_html(i, c) for i, c in enumerate(cards))}
<footer>Informe generado localmente por <a href="{_h(REPO_URL)}">Etch-DB-Mapper</a>. Contiene nombres de tablas y columnas, tipos, relaciones y notas; no incluye datos de las tablas ni credenciales.
Las relaciones probables se deducen por nombre y no son claves foráneas reales.</footer></div>
<script type="application/json" id="etch-data">{payload}</script>{scripts}
</body></html>
"""
