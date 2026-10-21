"""Camino entre dos tablas y generador de JOIN.

Con el grafo de claves foráneas (y, si se pide, las relaciones probables de
`core/inference.py`) busca los caminos más cortos entre dos tablas y arma el SQL
para unirlas. Solo *genera texto*: no ejecuta nada contra la base.

Los caminos que usan relaciones probables se marcan y se ordenan después de los que
solo usan claves reales.
"""
import re

_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_EXPANSIONS = 40000


def quote_ident(engine: str, name: str) -> str:
    if _PLAIN.match(name):
        return name
    if engine == "mssql":
        return "[" + name.replace("]", "]]") + "]"
    if engine == "mysql":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def _adjacency(tables: dict, inferred: list, include_inferred: bool) -> dict:
    adj = {n: [] for n in tables}

    def add(a, acol, b, bcol, is_inferred):
        if a not in tables or b not in tables or a == b:
            return
        adj[a].append({"left": a, "left_col": acol, "right": b, "right_col": bcol, "inferred": is_inferred})
        adj[b].append({"left": b, "left_col": bcol, "right": a, "right_col": acol, "inferred": is_inferred})

    for name, t in tables.items():
        for r in t["relations"]:
            add(name, r["col"], r["ref_table"], r["ref_col"], False)
    if include_inferred:
        seen = {(e["left"], e["left_col"], e["right"], e["right_col"]) for edges in adj.values() for e in edges}
        for r in inferred:
            if (r["table"], r["col"], r["ref_table"], r["ref_col"]) not in seen:
                add(r["table"], r["col"], r["ref_table"], r["ref_col"], True)
    return adj


def find_paths(tables: dict, inferred: list, source: str, target: str, include_inferred: bool = True,
               limit: int = 5, extra_hops: int = 1, max_len: int = 7) -> list:
    """Hasta `limit` caminos simples source -> target, los más cortos primero (permite
    `extra_hops` saltos más que el mínimo). Cada camino es una lista de pasos
    {left, left_col, right, right_col, inferred}."""
    if source not in tables or target not in tables or source == target:
        return []
    adj = _adjacency(tables, inferred, include_inferred)

    # distancia mínima (BFS) para acotar la búsqueda
    dist, frontier = {source: 0}, [source]
    while frontier and target not in dist:
        nxt = []
        for n in frontier:
            for e in adj[n]:
                if e["right"] not in dist:
                    dist[e["right"]] = dist[n] + 1
                    nxt.append(e["right"])
        frontier = nxt
    if target not in dist:
        return []
    cap = min(max_len, dist[target] + extra_hops)

    found, budget = [], [MAX_EXPANSIONS]

    def dfs(node, visited, path):
        if budget[0] <= 0:
            return
        budget[0] -= 1
        if node == target:
            found.append(list(path))
            return
        if len(path) >= cap:
            return
        for e in adj[node]:
            if e["right"] in visited:
                continue
            visited.add(e["right"])
            path.append(e)
            dfs(e["right"], visited, path)
            path.pop()
            visited.discard(e["right"])

    dfs(source, {source}, [])
    found.sort(key=lambda p: (sum(1 for s in p if s["inferred"]), len(p), [s["right"] for s in p]))
    unique, seen = [], set()
    for p in found:
        key = tuple((s["left"], s["left_col"], s["right"], s["right_col"]) for s in p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:limit]


def _qualified(engine: str, tables: dict, key: str) -> str:
    info = tables[key]
    schema = info.get("schema") or ""
    name = info.get("name") or key
    if schema and schema != "main":
        return quote_ident(engine, schema) + "." + quote_ident(engine, name)
    return quote_ident(engine, name)


def join_sql(engine: str, tables: dict, path: list) -> str:
    """SQL con INNER JOIN a lo largo del camino. Los alias son t1, t2…"""
    if not path:
        return ""
    names = [path[0]["left"]] + [s["right"] for s in path]
    chain = " → ".join(names)
    lines = [f"-- Camino: {chain}"]
    inferred = [s for s in path if s["inferred"]]
    if inferred:
        lines.append("-- OJO: usa relaciones PROBABLES (deducidas por nombre, no son claves foráneas reales): "
                     + ", ".join(f"{s['left']}.{s['left_col']} = {s['right']}.{s['right_col']}" for s in inferred))
    lines.append("-- Ajusta las columnas del SELECT según lo que necesites.")
    lines.append("SELECT *")
    lines.append(f"FROM {_qualified(engine, tables, names[0])} AS t1")
    for i, s in enumerate(path, start=2):
        lines.append(
            f"INNER JOIN {_qualified(engine, tables, s['right'])} AS t{i} "
            f"ON t{i - 1}.{quote_ident(engine, s['left_col'])} = t{i}.{quote_ident(engine, s['right_col'])}"
        )
    return "\n".join(lines) + ";"
