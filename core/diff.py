"""Comparación de dos versiones del esquema (formas compactas de
`storage.compact_schema`): qué tablas, columnas y relaciones cambiaron."""


def diff_schemas(old: dict, new: dict) -> dict:
    old, new = old or {}, new or {}
    added = sorted(n for n in new if n not in old)
    removed = sorted(n for n in old if n not in new)
    changed = {}
    for name in sorted(set(old) & set(new)):
        oc = {c[0]: c for c in old[name]["c"]}
        nc = {c[0]: c for c in new[name]["c"]}
        added_cols = [{"name": n, "type": nc[n][1], "null": nc[n][2], "pk": nc[n][3]} for n in nc if n not in oc]
        removed_cols = [{"name": n, "type": oc[n][1]} for n in oc if n not in nc]
        modified = []
        for n in oc.keys() & nc.keys():
            a, b = oc[n], nc[n]
            changes = {}
            if a[1] != b[1]:
                changes["type"] = [a[1], b[1]]
            if a[2] != b[2]:
                changes["null"] = [a[2], b[2]]
            if a[3] != b[3]:
                changes["pk"] = [a[3], b[3]]
            if changes:
                modified.append({"name": n, "changes": changes})
        orel = {tuple(r) for r in old[name]["r"]}
        nrel = {tuple(r) for r in new[name]["r"]}
        added_rel = [list(r) for r in sorted(nrel - orel)]
        removed_rel = [list(r) for r in sorted(orel - nrel)]
        if added_cols or removed_cols or modified or added_rel or removed_rel:
            changed[name] = {"added_columns": added_cols, "removed_columns": removed_cols, "modified_columns": modified,
                             "added_relations": added_rel, "removed_relations": removed_rel}
    summary = {
        "added_tables": len(added), "removed_tables": len(removed), "changed_tables": len(changed),
        "added_columns": sum(len(c["added_columns"]) for c in changed.values()),
        "removed_columns": sum(len(c["removed_columns"]) for c in changed.values()),
        "modified_columns": sum(len(c["modified_columns"]) for c in changed.values()),
        "added_relations": sum(len(c["added_relations"]) for c in changed.values()),
        "removed_relations": sum(len(c["removed_relations"]) for c in changed.values()),
    }
    summary["total"] = sum(v for k, v in summary.items() if k != "changed_tables")
    return {
        "added_tables": [{"name": n, "columns": len(new[n]["c"]), "relations": len(new[n]["r"])} for n in added],
        "removed_tables": [{"name": n, "columns": len(old[n]["c"]), "relations": len(old[n]["r"])} for n in removed],
        "changed_tables": changed,
        "summary": summary,
    }


def describe(summary: dict) -> str:
    """Resumen corto para un aviso: '+2 tablas, 1 columna nueva, 3 relaciones nuevas'."""
    parts = []

    def add(n, one, many):
        if n:
            parts.append(f"{n} {one if n == 1 else many}")

    add(summary["added_tables"], "tabla nueva", "tablas nuevas")
    add(summary["removed_tables"], "tabla eliminada", "tablas eliminadas")
    add(summary["added_columns"], "columna nueva", "columnas nuevas")
    add(summary["removed_columns"], "columna eliminada", "columnas eliminadas")
    add(summary["modified_columns"], "columna modificada", "columnas modificadas")
    add(summary["added_relations"] + summary["removed_relations"], "cambio de relaciones", "cambios de relaciones")
    return ", ".join(parts) or "sin cambios"
