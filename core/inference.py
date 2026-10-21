"""Relaciones inferidas por nombre.

Muchas bases (sobre todo las antiguas) no declaran FOREIGN KEY: el vínculo entre
tablas existe solo "por convención" (una columna `ClienteID` en `Pedido`).
Acá se proponen esas relaciones a partir de los nombres y los tipos del esquema
ya leído; no se consulta la base de nuevo y **nunca se escribe nada en ella**.

Son *sugerencias*: se muestran aparte de las claves foráneas reales (línea
punteada en el mapa) y se pueden ocultar.

Reglas
------
1. Se ignoran las columnas que ya son una FK declarada.
2. Alta confianza: la columna se llama igual que la clave primaria (de una sola
   columna, con nombre no genérico y única en el esquema) de otra tabla y los
   tipos son compatibles. Ej.: `Orders.CustomerID` ↔ `Customers.CustomerID`.
3. Media confianza: el nombre de la columna sin su sufijo (`ID`, `Key`, `Cod`,
   `Codigo`, `Ref`, `No`…) coincide con el nombre de una tabla (con o sin
   prefijo como `tbl_`, `Cat_`, singular o plural) y los tipos son compatibles.
4. Si hay varias tablas candidatas se prefiere la del mismo prefijo que la tabla
   origen; si sigue habiendo empate, no se sugiere nada (mejor omitir que errar).
"""
import re

GENERIC_PK = {"id", "uid", "uuid", "guid", "key", "pk", "rowid", "oid"}
ID_SUFFIXES = {"id", "key", "cod", "codigo", "code", "ref", "fk", "no", "num", "nro", "number", "uid", "guid"}
NOISE_PREFIXES = {"tbl", "tb", "t", "dim", "fact", "vw", "sys", "cat", "cfg", "tmp", "log", "rpt"}

_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")

_INT = {"int", "integer", "bigint", "smallint", "tinyint", "serial", "bigserial", "int2", "int4", "int8", "mediumint", "number"}
_STR = {"varchar", "char", "nvarchar", "nchar", "text", "ntext", "character", "string", "varchar2", "bpchar", "citext"}
_UUID = {"uuid", "uniqueidentifier", "guid"}


def _tokens(name: str) -> list:
    return [t.lower() for t in _TOKEN.findall(name or "")]


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _family(col_type: str) -> str:
    base = re.split(r"[\s(\[]", (col_type or "").strip().lower(), maxsplit=1)[0]
    if base in _INT:
        return "int"
    if base in _STR:
        return "str"
    if base in _UUID:
        return "uuid"
    return base or "?"


def _stem(column: str):
    """'ClienteID' -> 'cliente'; None si no termina en un sufijo de clave."""
    toks = _tokens(column)
    while toks and toks[-1].isdigit():
        toks.pop()
    if len(toks) < 2 or toks[-1] not in ID_SUFFIXES:
        return None
    return _singular("".join(toks[:-1]))


def _table_variants(name: str) -> dict:
    """variante normalizada -> puntaje (3 = nombre completo, 2 = sin prefijo)."""
    toks = _tokens(name)
    variants = {}
    full = "".join(toks)
    variants[_singular(full)] = 3
    if len(toks) >= 2:
        variants.setdefault(_singular("".join(toks[1:])), 2)
        if toks[0] in NOISE_PREFIXES or len(toks[0]) <= 3:
            variants[_singular("".join(toks[1:]))] = 2
    return variants


def _prefix(name: str) -> str:
    toks = _tokens(name)
    return toks[0] if len(toks) >= 2 else ""


def infer_relations(tables: dict) -> list:
    """tables: esquema normalizado (finalize_schema). Devuelve una lista de
    {table, col, ref_table, ref_col, confidence: 'high'|'medium', reason}."""
    # clave primaria de una sola columna por tabla, y cuántas tablas la usan
    single_pk = {}
    pk_name_count = {}
    for name, t in tables.items():
        pks = [c for c in t["columns"] if c["pk"]]
        if len(pks) == 1:
            single_pk[name] = pks[0]
            pk_name_count[pks[0]["name"].lower()] = pk_name_count.get(pks[0]["name"].lower(), 0) + 1

    index = {}
    for name in tables:
        for variant, score in _table_variants(name).items():
            if len(variant) >= 3:
                index.setdefault(variant, []).append((name, score))
    unique_pk_owner = {}
    for name, pk in single_pk.items():
        if pk_name_count[pk["name"].lower()] == 1 and pk["name"].lower() not in GENERIC_PK:
            unique_pk_owner[pk["name"].lower()] = name

    found = []
    for tname, t in tables.items():
        declared = {r["col"] for r in t["relations"]}
        own_pk = single_pk.get(tname)
        for col in t["columns"]:
            cname = col["name"]
            if cname in declared or (own_pk is not None and own_pk["name"] == cname):
                continue
            hit = None

            owner = unique_pk_owner.get(cname.lower())
            if owner and owner != tname and _family(col["type"]) == _family(single_pk[owner]["type"]):
                hit = (owner, single_pk[owner]["name"], "high", f"Misma columna que la clave primaria de {owner}")

            if hit is None:
                stem = _stem(cname)
                cands = index.get(stem) if stem and len(stem) >= 3 else None
                if cands:
                    best = max(s for _n, s in cands)
                    top = sorted({n for n, s in cands if s == best and n != tname})
                    if len(top) > 1:
                        same = [n for n in top if _prefix(n) and _prefix(n) == _prefix(tname)]
                        top = same if len(same) == 1 else []
                    if len(top) == 1:
                        target = top[0]
                        tcol = single_pk.get(target)
                        if tcol is None:
                            tcol = next((c for c in tables[target]["columns"] if c["name"].lower() == cname.lower()), None)
                        if tcol is not None and _family(col["type"]) == _family(tcol["type"]):
                            hit = (target, tcol["name"], "medium", f"El nombre de la columna apunta a la tabla {target}")
            if hit:
                found.append({"table": tname, "col": cname, "ref_table": hit[0], "ref_col": hit[1], "confidence": hit[2], "reason": hit[3]})
    found.sort(key=lambda r: (r["confidence"] != "high", r["table"], r["col"]))
    return found
