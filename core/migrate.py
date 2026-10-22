"""Migración, fase 1: generar el script de creación de tablas para otro motor.

Esta fase **solo produce texto**: a partir del esquema ya escaneado arma un script
SQL (`CREATE TABLE`, claves, UNIQUE, identidades, valores por defecto y descripciones)
para el motor de destino. No se conecta a ningún destino y no escribe en ninguna base.

Reglas de seguridad del script generado:
* Solo contiene sentencias que CREAN objetos nuevos (CREATE SCHEMA, CREATE TABLE,
  ALTER TABLE ... ADD CONSTRAINT, comentarios). Jamás DROP, TRUNCATE, DELETE ni UPDATE.
* No usa `IF NOT EXISTS`: si algo ya existe en el destino, el script falla en vez de
  saltarse o pisar silenciosamente.

Lo que NO migra todavía (se avisa en el informe): índices no únicos, CHECK, reglas
ON DELETE/ON UPDATE (se usa la acción por defecto), vistas, procedimientos, triggers y
los datos. Cada traducción con pérdida o suposición genera una advertencia.
"""
import hashlib
import re
from datetime import datetime

from .version import __version__

TARGETS = {"postgres": "PostgreSQL", "mssql": "SQL Server", "mysql": "MySQL / MariaDB", "sqlite": "SQLite"}
MAX_IDENT = {"postgres": 63, "mssql": 128, "mysql": 64, "sqlite": None}
DEFAULT_SCHEMAS = {"", "main", "dbo", "public"}
RESERVED = {
    "user", "order", "group", "table", "select", "where", "from", "to", "desc", "asc", "index", "key", "primary", "references",
    "check", "default", "column", "constraint", "create", "drop", "insert", "update", "delete", "join", "left", "right", "inner",
    "union", "limit", "offset", "case", "when", "then", "end", "all", "and", "or", "not", "null", "in", "is", "like", "between",
    "exists", "having", "into", "values", "set", "view", "schema", "database", "grant", "role", "with", "as", "by", "on", "using",
}
_PLAIN = re.compile(r"^[a-z_][a-z0-9_]*$")
_OPTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,60}$")


# --------------------------------------------------------------------- tipos
_INT = {"int": "int", "integer": "int", "int4": "int", "mediumint": "int", "serial": "int", "bigint": "bigint", "int8": "bigint",
        "bigserial": "bigint", "smallint": "smallint", "int2": "smallint", "smallserial": "smallint", "tinyint": "tinyint", "year": "smallint"}
_DEC = {"numeric", "decimal", "dec", "number"}
_FLOAT = {"real": "real", "float4": "real", "float": "double", "double": "double", "double precision": "double", "float8": "double"}
_BOOL = {"bit", "boolean", "bool"}
_CHAR = {"char", "character", "bpchar", "nchar"}
_VARCHAR = {"varchar", "character varying", "nvarchar", "varchar2", "nvarchar2"}
_TEXT = {"text", "tinytext", "mediumtext", "longtext", "ntext", "clob", "citext"}
_DATETIME = {"datetime", "datetime2", "smalldatetime", "timestamp without time zone"}
_DATETIMETZ = {"timestamptz", "datetimeoffset", "timestamp with time zone"}
_BINARY = {"binary", "varbinary", "blob", "tinyblob", "mediumblob", "longblob", "bytea", "image"}


def parse_type(type_str: str, prec, source_engine: str) -> dict:
    """Tipo de texto ('varchar(50)', 'numeric', 'timestamptz'…) -> categoría común + parámetros."""
    t = (type_str or "").strip().lower()
    m = re.match(r"^([a-z_][a-z_ \-]*?)\s*(?:\(\s*([^)]*)\))?\s*(?:unsigned)?\s*$", t)
    base, params = (m.group(1).strip(), m.group(2)) if m else (t, None)
    nums = []
    if params:
        for x in params.split(","):
            x = x.strip()
            nums.append("max" if x == "max" else int(x) if x.isdigit() else None)
    length = nums[0] if nums else None
    unicode_ = base.startswith("n") and base in {"nchar", "nvarchar", "ntext", "nvarchar2"}
    out = {"base": base, "len": length, "p": None, "s": None, "unicode": unicode_, "kind": "other"}
    if base in _INT:
        out["kind"] = _INT[base]
    elif base in _DEC:
        out["kind"] = "decimal"
        if prec:
            out["p"], out["s"] = prec[0], prec[1]
        elif len(nums) >= 1 and isinstance(nums[0], int):
            out["p"], out["s"] = nums[0], (nums[1] if len(nums) > 1 and isinstance(nums[1], int) else 0)
    elif base in ("money", "smallmoney"):
        out["kind"] = "money"
    elif base in _FLOAT:
        out["kind"] = _FLOAT[base]
    elif base in _BOOL:
        out["kind"] = "bool"
    elif base in _CHAR:
        out["kind"] = "char"
    elif base in _VARCHAR:
        out["kind"] = "varchar"
    elif base in _TEXT:
        out["kind"] = "text"
    elif base == "date":
        out["kind"] = "date"
    elif base in ("time", "timetz", "time without time zone", "time with time zone"):
        out["kind"] = "time"
    elif base == "timestamp":
        out["kind"] = "rowversion" if source_engine == "mssql" else "datetime"
    elif base == "rowversion":
        out["kind"] = "rowversion"
    elif base in _DATETIME:
        out["kind"] = "datetime"
    elif base in _DATETIMETZ:
        out["kind"] = "datetimetz"
    elif base in ("uuid", "uniqueidentifier", "guid"):
        out["kind"] = "uuid"
    elif base in _BINARY:
        out["kind"] = "binary"
    elif base in ("json", "jsonb"):
        out["kind"] = "json"
    elif base == "xml":
        out["kind"] = "xml"
    elif base in ("enum", "set"):
        out["kind"] = "enum"
    return out


def _n(length, default=None):
    return length if isinstance(length, int) else default


def render_type(ti: dict, target: str, source_engine: str) -> tuple:
    """Categoría -> (tipo SQL del destino, [notas de advertencia])."""
    k, notes = ti["kind"], []
    ln, p, s = ti["len"], ti["p"], ti["s"]

    if k in ("int", "bigint", "smallint", "tinyint"):
        sql = {"postgres": {"int": "INTEGER", "bigint": "BIGINT", "smallint": "SMALLINT", "tinyint": "SMALLINT"},
               "mssql": {"int": "INT", "bigint": "BIGINT", "smallint": "SMALLINT", "tinyint": "TINYINT"},
               "mysql": {"int": "INT", "bigint": "BIGINT", "smallint": "SMALLINT", "tinyint": "TINYINT"},
               "sqlite": {"int": "INTEGER", "bigint": "INTEGER", "smallint": "INTEGER", "tinyint": "INTEGER"}}[target][k]
        return sql, notes
    if k in ("decimal", "money"):
        if k == "money":
            p, s = 19, 4
        if p is None:
            if target == "postgres":
                return "NUMERIC", notes + ["Sin precisión conocida: se usa NUMERIC sin límites. Reescanea para leerla."]
            if target == "sqlite":
                return "NUMERIC", notes
            fallback = (38, 10) if target == "mssql" else (30, 10)
            return f"DECIMAL({fallback[0]},{fallback[1]})", notes + [f"Sin precisión conocida: se usa DECIMAL({fallback[0]},{fallback[1]}). Reescanea la conexión para leerla."]
        cap = {"mssql": 38, "mysql": 65}.get(target)
        if cap and p > cap:
            notes.append(f"Precisión {p} supera el máximo de {TARGETS[target]} ({cap}): se recorta.")
            p = cap
        if target == "mysql" and s > 30:
            notes.append("Escala mayor que 30: se recorta a 30.")
            s = 30
        if target == "sqlite":
            return "NUMERIC", notes
        return (f"NUMERIC({p},{s})" if target == "postgres" else f"DECIMAL({p},{s})"), notes
    if k == "real":
        return {"postgres": "REAL", "mssql": "REAL", "mysql": "FLOAT", "sqlite": "REAL"}[target], notes
    if k == "double":
        return {"postgres": "DOUBLE PRECISION", "mssql": "FLOAT", "mysql": "DOUBLE", "sqlite": "REAL"}[target], notes
    if k == "bool":
        return {"postgres": "BOOLEAN", "mssql": "BIT", "mysql": "TINYINT(1)", "sqlite": "INTEGER"}[target], notes
    if k in ("char", "varchar", "text"):
        return _render_string(ti, target, source_engine)
    if k == "date":
        return "DATE", notes
    if k == "time":
        return ("TEXT" if target == "sqlite" else "TIME"), notes
    if k == "datetime":
        return {"postgres": "TIMESTAMP", "mssql": "DATETIME2", "mysql": "DATETIME", "sqlite": "DATETIME"}[target], notes
    if k == "datetimetz":
        if target == "mysql":
            notes.append("MySQL no guarda la zona horaria: usa DATETIME y conviene guardar todo en UTC.")
        if target == "sqlite":
            notes.append("SQLite guarda las fechas como texto: se pierde el tipo con zona horaria.")
        return {"postgres": "TIMESTAMPTZ", "mssql": "DATETIMEOFFSET", "mysql": "DATETIME", "sqlite": "DATETIME"}[target], notes
    if k == "rowversion":
        if target == "mssql" and source_engine == "mssql":
            return "ROWVERSION", notes
        notes.append("rowversion/timestamp de SQL Server es un contador binario interno, no una fecha: se crea como binario y no se puede copiar con sentido.")
        return {"postgres": "BYTEA", "mssql": "VARBINARY(8)", "mysql": "BINARY(8)", "sqlite": "BLOB"}[target], notes
    if k == "uuid":
        return {"postgres": "UUID", "mssql": "UNIQUEIDENTIFIER", "mysql": "CHAR(36)", "sqlite": "TEXT"}[target], notes
    if k == "binary":
        if target == "postgres":
            return "BYTEA", notes
        if target == "sqlite":
            return "BLOB", notes
        if target == "mssql":
            return (f"VARBINARY({ln})" if isinstance(ln, int) and ln <= 8000 else "VARBINARY(MAX)"), notes
        return (f"VARBINARY({ln})" if isinstance(ln, int) and ln <= 65535 else "LONGBLOB"), notes
    if k == "json":
        if target == "mssql":
            notes.append("SQL Server no tiene tipo JSON propio: se guarda como NVARCHAR(MAX).")
        return {"postgres": "JSONB" if ti["base"] == "jsonb" else "JSON", "mssql": "NVARCHAR(MAX)", "mysql": "JSON", "sqlite": "TEXT"}[target], notes
    if k == "xml":
        if target == "mysql":
            notes.append("MySQL no tiene tipo XML: se guarda como LONGTEXT.")
        return {"postgres": "XML", "mssql": "XML", "mysql": "LONGTEXT", "sqlite": "TEXT"}[target], notes
    if k == "enum":
        notes.append("ENUM/SET no se traduce (se pierden los valores permitidos): se usa texto.")
        return {"postgres": "VARCHAR(255)", "mssql": "NVARCHAR(255)", "mysql": "VARCHAR(255)", "sqlite": "TEXT"}[target], notes
    notes.append(f"Tipo «{ti['base'] or '?'}» sin equivalente claro: se usa texto largo. Revísalo a mano.")
    return {"postgres": "TEXT", "mssql": "NVARCHAR(MAX)", "mysql": "LONGTEXT", "sqlite": "TEXT"}[target], notes


def _render_string(ti: dict, target: str, source_engine: str) -> tuple:
    k, ln, notes = ti["kind"], ti["len"], []
    n = _n(ln)
    if target == "sqlite":
        return "TEXT", notes
    if target == "postgres":
        if k == "text" or n is None:
            return "TEXT", notes
        return (f"CHAR({n})" if k == "char" else f"VARCHAR({n})"), notes
    if target == "mssql":
        uni = ti["unicode"] or source_engine != "mssql"   # PostgreSQL/MySQL/SQLite guardan Unicode: NVARCHAR evita perder caracteres
        pre, cap = ("N", 4000) if uni else ("", 8000)
        if k == "text" or n is None:
            return f"{pre}VARCHAR(MAX)", notes
        if n > cap:
            return f"{pre}VARCHAR(MAX)", notes
        return (f"{pre}CHAR({n})" if k == "char" else f"{pre}VARCHAR({n})"), notes
    # mysql
    if k == "text" or n is None:
        return "LONGTEXT", notes
    if k == "char" and n <= 255:
        return f"CHAR({n})", notes
    if n > 16000:
        notes.append(f"VARCHAR({n}) no cabe en una fila de MySQL (utf8mb4): se usa LONGTEXT.")
        return "LONGTEXT", notes
    return f"VARCHAR({n})", notes


# ---------------------------------------------------------------- defaults
_NOW = re.compile(r"^(now\(\)|current_timestamp(\(\d*\))?|getdate\(\)|sysdatetime\(\)|sysdatetimeoffset\(\)|localtimestamp(\(\d*\))?|getutcdate\(\)|current_timestamp\(\))$", re.I)
_TODAY = re.compile(r"^(current_date|curdate\(\)|cast\(getdate\(\) as date\)|convert\(date,getdate\(\)\))$", re.I)
_UUIDF = re.compile(r"^(newid\(\)|newsequentialid\(\)|gen_random_uuid\(\)|uuid_generate_v4\(\)|uuid\(\))$", re.I)


def _strip_default(raw: str) -> str:
    d = raw.strip()
    while d.startswith("(") and d.endswith(")") and _balanced(d[1:-1]):
        d = d[1:-1].strip()
    d = re.sub(r"^N'", "'", d)
    m = re.match(r"^('(?:[^']|'')*')::[a-zA-Z_ ]+(\(\d+(,\d+)?\))?(\[\])?$", d)
    if m:
        d = m.group(1)
    return d


def _balanced(s: str) -> bool:
    depth = 0
    for ch in s:
        depth += ch == "("
        depth -= ch == ")"
        if depth < 0:
            return False
    return depth == 0


def translate_default(raw, kind: str, target: str, source_engine: str):
    """-> (expresión SQL | None, advertencia | None). Solo traduce lo que sabe hacer sin riesgo."""
    if raw is None:
        return None, None
    d = _strip_default(str(raw))
    if not d or d.upper() == "NULL":
        return None, None
    if _UUIDF.match(d):
        if kind != "uuid":
            return None, f"Valor por defecto «{d}» omitido: la columna no es UUID."
        return {"postgres": "gen_random_uuid()", "mssql": "NEWID()", "mysql": "(UUID())"}.get(target), \
            (None if target != "sqlite" else "Valor por defecto de UUID omitido: SQLite no genera UUID.")
    if _NOW.match(d):
        if kind not in ("datetime", "datetimetz"):
            return None, f"Valor por defecto «{d}» omitido: la columna no es de fecha y hora."
        return {"postgres": "CURRENT_TIMESTAMP", "mssql": "SYSDATETIME()" if kind == "datetime" else "SYSDATETIMEOFFSET()",
                "mysql": "CURRENT_TIMESTAMP", "sqlite": "CURRENT_TIMESTAMP"}[target], None
    if _TODAY.match(d):
        if kind != "date":
            return None, f"Valor por defecto «{d}» omitido: la columna no es DATE."
        return {"postgres": "CURRENT_DATE", "mssql": "CAST(GETDATE() AS DATE)", "mysql": "(CURRENT_DATE)", "sqlite": "CURRENT_DATE"}[target], \
            ("Valor por defecto CURRENT_DATE en MySQL requiere la versión 8.0.13 o superior." if target == "mysql" else None)
    low = d.lower()
    if kind == "bool":
        if low in ("true", "1", "b'1'", "'t'", "'true'", "'1'"):
            return ("true" if target == "postgres" else "1"), None
        if low in ("false", "0", "b'0'", "'f'", "'false'", "'0'"):
            return ("false" if target == "postgres" else "0"), None
    if re.match(r"^-?\d+(\.\d+)?$", d):
        if kind in ("int", "bigint", "smallint", "tinyint", "decimal", "money", "real", "double"):
            return d, None
        if kind in ("char", "varchar", "text"):
            return "'" + d + "'", None
        return None, f"Valor por defecto numérico «{d}» omitido: no encaja con el tipo de la columna."
    if re.match(r"^'(?:[^']|'')*'$", d) and kind in ("char", "varchar", "text", "date", "time", "datetime", "datetimetz", "uuid", "enum", "other"):
        return d, None
    if source_engine == "mysql" and re.match(r"^[\w .:-]*$", d) and kind in ("char", "varchar", "text", "enum"):
        return "'" + d.replace("'", "''") + "'", None   # MySQL devuelve los literales sin comillas
    return None, f"Valor por defecto «{str(raw)[:60]}» no se tradujo (revísalo y agrégalo a mano si hace falta)."


# ------------------------------------------------------------ nombres y SQL
class _Namer:
    def __init__(self, target: str, style: str, warnings: list):
        self.target, self.style, self.warn = target, style, warnings
        self.limit = MAX_IDENT[target]

    def fit(self, name: str, where: dict) -> str:
        if self.limit and len(name) > self.limit:
            short = name[: self.limit - 9] + "_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
            self.warn.append({"level": "error", "message": f"El nombre «{name}» supera el máximo de {self.limit} caracteres de {TARGETS[self.target]}: se recortó a «{short}».", **where})
            return short
        return name

    def raw(self, name: str) -> str:
        return name.lower() if self.style == "lower" else name

    def q(self, name: str) -> str:
        if self.style == "lower" and self.target in ("postgres", "sqlite") and _PLAIN.match(name) and name not in RESERVED:
            return name
        if self.target == "mssql":
            return "[" + name.replace("]", "]]") + "]"
        if self.target == "mysql":
            return "`" + name.replace("`", "``") + "`"
        return '"' + name.replace('"', '""') + '"'


def _lit(text: str, target: str) -> str:
    t = str(text).replace("'", "''")
    return ("N'" + t + "'") if target == "mssql" else ("'" + t + "'")


def _topo(names: list, deps: dict) -> list:
    """Orden de creación: padres antes que hijos. Los ciclos se dejan al final (las FK se agregan aparte)."""
    remaining, ordered = set(names), []
    while remaining:
        ready = sorted(n for n in remaining if not (deps.get(n, set()) & remaining) - {n})
        if not ready:
            ready = sorted(remaining)[:1]
        for n in ready:
            ordered.append(n)
            remaining.discard(n)
    return ordered


def generate_ddl(tables: dict, source_engine: str, target: str, options: dict = None, alias: str = "", descriptions: dict = None) -> dict:
    """Esquema normalizado (finalize_schema) -> {"sql", "warnings", "stats", "tables", "target", "options"}.

    options: name_style ('keep'|'lower'), target_schema, table_prefix, only (lista de tablas),
    include_fks / include_uniques / include_defaults / include_identity / include_comments (bool).
    descriptions: {tabla: {"table": texto, "columns": {col: texto}}} (notas del usuario > comentarios de la base).
    """
    if target not in TARGETS:
        raise ValueError("Elige un motor de destino: " + ", ".join(TARGETS.values()) + ".")
    opts = {"name_style": "lower" if target == "postgres" else "keep", "target_schema": "", "table_prefix": "", "only": None,
            "include_fks": True, "include_uniques": True, "include_defaults": True, "include_identity": True, "include_comments": True}
    opts.update({k: v for k, v in (options or {}).items() if k in opts and v is not None})
    if opts["name_style"] not in ("keep", "lower"):
        raise ValueError("Estilo de nombres no válido.")
    for key in ("target_schema", "table_prefix"):
        opts[key] = (opts[key] or "").strip()
        if opts[key] and not _OPTION_NAME.match(opts[key]):
            raise ValueError("El esquema y el prefijo solo pueden llevar letras, números y guion bajo (máx. 60, sin empezar por número).")

    warnings: list = []

    def warn(level, message, table=None, column=None):
        warnings.append({"level": level, "table": table, "column": column, "message": message})

    namer = _Namer(target, opts["name_style"], warnings)
    selected = [n for n in tables if (not opts["only"] or n in opts["only"])]
    if not selected:
        raise ValueError("No hay tablas para migrar.")
    sel = set(selected)
    descriptions = descriptions or {}

    # ---- nombres de destino de las tablas (esquema / prefijo / aplanado) ----
    use_schema = target in ("postgres", "mssql")
    if opts["target_schema"] and not use_schema:
        warn("info", f"{TARGETS[target]} no tiene esquemas separados: se ignora «{opts['target_schema']}» (usa el prefijo de tablas para aislarlas).")
    flattened = False
    tinfo = {}
    for n in selected:
        t = tables[n]
        real = t.get("name") or n
        src_schema = (t.get("schema") or "").strip()
        schema = None
        prefix = opts["table_prefix"]
        if use_schema and opts["target_schema"]:
            schema = opts["target_schema"]
        elif src_schema.lower() not in DEFAULT_SCHEMAS:
            if use_schema:
                schema = src_schema
            else:
                prefix = prefix + src_schema + "_"
                flattened = True
        tinfo[n] = {"schema": schema, "name": namer.fit(namer.raw(prefix + real), {"table": n, "column": None})}
    if flattened:
        warn("info", "Hay tablas en esquemas distintos del principal y el destino no tiene esquemas: se antepone el nombre del esquema al de la tabla.")
    schemas = sorted({v["schema"] for v in tinfo.values() if v["schema"]}) if use_schema else []

    seen_names = {}
    for n, v in tinfo.items():
        key = ((v["schema"] or "").lower(), v["name"].lower())
        if key in seen_names:
            warn("error", f"Dos tablas de origen («{seen_names[key]}» y «{n}») terminan con el mismo nombre en el destino. Cambia el prefijo o el esquema.", n)
        seen_names[key] = n

    def qname(n):
        v = tinfo[n]
        return (namer.q(v["schema"]) + "." if v["schema"] else "") + namer.q(v["name"])

    # ---- columnas que actúan como clave (PK, UNIQUE, FK local o referenciada): en SQL Server/MySQL el tipo debe poder indexarse ----
    keyish = set()
    for n in selected:
        t = tables[n]
        keyish.update((n, c["name"]) for c in t["columns"] if c["pk"])
        keyish.update((n, cname) for u in t.get("uniques", []) for cname in u)
        for r in t["relations"]:
            if r["ref_table"] in sel:
                keyish.add((n, r["col"]))
                keyish.add((r["ref_table"], r["ref_col"]))

    # ---- columnas ----
    tables_out, create_blocks, fk_blocks, desc_blocks = [], {}, [], []
    stats = {"tables": 0, "columns": 0, "foreign_keys": 0, "uniques": 0, "identities": 0, "defaults": 0}
    col_target = {}
    for n in selected:
        t = tables[n]
        cols_sql, cols_out, used = [], [], {}
        pk_cols = [c["name"] for c in t["columns"] if c["pk"]]
        sqlite_inline_pk = False
        for c in t["columns"]:
            where = {"table": n, "column": c["name"]}
            ti = parse_type(c.get("type"), c.get("prec"), source_engine)
            tsql, notes = render_type(ti, target, source_engine)
            for note in notes:
                warn("warn", note, n, c["name"])
            if (n, c["name"]) in keyish and ti["kind"] in ("char", "varchar", "text", "enum", "other", "json", "xml") and target in ("mssql", "mysql"):
                bounded, bnote = _bound_key_type(tsql, target)
                if bounded:
                    tsql = bounded
                    warn("warn", bnote, n, c["name"])
            if ti["kind"] == "other" and not notes:
                warn("warn", f"Tipo «{c.get('type')}» desconocido.", n, c["name"])
            cname = namer.fit(namer.raw(c["name"]), where)
            if cname.lower() in used:
                warn("error", f"Dos columnas («{used[cname.lower()]}» y «{c['name']}») quedan con el mismo nombre en el destino.", n, c["name"])
            used[cname.lower()] = c["name"]
            col_target[(n, c["name"])] = cname

            parts = [namer.q(cname), tsql]
            identity = bool(c.get("identity")) and opts["include_identity"]
            inline_pk = False
            if c.get("identity") and not opts["include_identity"]:
                warn("info", "Columna de identidad creada como número normal (identidad desactivada en las opciones).", n, c["name"])
            if identity:
                if ti["kind"] not in ("int", "bigint", "smallint", "tinyint", "decimal"):
                    warn("warn", "Identidad/autoincremento omitido: el tipo de la columna no lo admite.", n, c["name"])
                    identity = False
                elif target == "postgres":
                    parts.append("GENERATED BY DEFAULT AS IDENTITY")
                elif target == "mssql":
                    parts.append("IDENTITY(1,1)")
                elif target == "mysql":
                    if len(pk_cols) == 1 and c["pk"]:
                        parts.append("AUTO_INCREMENT")
                    else:
                        warn("warn", "AUTO_INCREMENT omitido: en MySQL la columna debe ser la clave primaria (o la primera de un índice).", n, c["name"])
                        identity = False
                elif target == "sqlite":
                    if len(pk_cols) == 1 and c["pk"] and tsql == "INTEGER":
                        inline_pk = sqlite_inline_pk = True
                    else:
                        warn("warn", "Autoincremento omitido: en SQLite solo una columna INTEGER que sea la clave primaria única lo admite.", n, c["name"])
                        identity = False
            if identity:
                stats["identities"] += 1
            if inline_pk:
                parts.append("PRIMARY KEY")
            elif not c["null"] or c["pk"]:
                parts.append("NOT NULL")
            if opts["include_defaults"] and not identity and c.get("default") is not None:
                dsql, dwarn = translate_default(c.get("default"), ti["kind"], target, source_engine)
                if dwarn:
                    warn("warn", dwarn, n, c["name"])
                if dsql and target == "mysql" and tsql in ("LONGTEXT", "LONGBLOB", "JSON") and not dsql.startswith("("):
                    warn("warn", "MySQL no admite un valor por defecto literal en columnas TEXT/BLOB/JSON: se omite.", n, c["name"])
                    dsql = None
                if dsql:
                    parts.append("DEFAULT " + dsql)
                    stats["defaults"] += 1
            if target == "mysql" and opts["include_comments"]:
                text = (descriptions.get(n, {}).get("columns", {}) or {}).get(c["name"]) or c.get("comment")
                if text:
                    parts.append("COMMENT " + _lit(text[:1000], target))
            cols_sql.append("  " + " ".join(parts))
            cols_out.append({"name": c["name"], "target_name": cname, "source_type": c.get("type") or "?", "target_type": tsql,
                             "identity": identity, "nullable": bool(c["null"]), "pk": bool(c["pk"])})
            stats["columns"] += 1

        constraints = []
        if pk_cols and not sqlite_inline_pk:
            constraints.append(f"  PRIMARY KEY ({', '.join(namer.q(col_target[(n, c)]) for c in pk_cols)})")
        elif not pk_cols:
            warn("info", "La tabla no tiene clave primaria (se crea igual, sin ella).", n)
        if opts["include_uniques"]:
            for u in t.get("uniques", []):
                if set(u) == set(pk_cols) or any(col not in {c['name'] for c in t['columns']} for col in u):
                    continue
                name = namer.fit(namer.raw("uq_" + tinfo[n]["name"] + "_" + "_".join(u)), {"table": n, "column": None})
                constraints.append(f"  CONSTRAINT {namer.q(name)} UNIQUE ({', '.join(namer.q(col_target[(n, col)]) for col in u)})")
                stats["uniques"] += 1
        inline_fks = []
        if opts["include_fks"]:
            for cols, ref, ref_cols in _group_fks(t, tables):
                if ref not in sel:
                    warn("warn", f"Clave foránea hacia «{ref}» omitida: esa tabla no está entre las migradas.", n, ", ".join(cols))
                    continue
                stats["foreign_keys"] += 1
                fk_name = namer.fit(namer.raw("fk_" + tinfo[n]["name"] + "_" + "_".join(cols)), {"table": n, "column": None})
                local = ", ".join(namer.q(col_target[(n, c)]) for c in cols)
                remote_cols = []
                for rc in ref_cols:
                    remote_cols.append(namer.q(col_target.get((ref, rc)) or namer.raw(rc)))
                clause = f"FOREIGN KEY ({local}) REFERENCES {qname(ref)} ({', '.join(remote_cols)})"
                if target == "sqlite":
                    inline_fks.append(f"  CONSTRAINT {namer.q(fk_name)} {clause}")
                else:
                    fk_blocks.append(f"ALTER TABLE {qname(n)} ADD CONSTRAINT {namer.q(fk_name)} {clause};")
        body = ",\n".join(cols_sql + constraints + inline_fks)
        suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if target == "mysql" else ""
        if target == "mysql" and opts["include_comments"]:
            ttext = (descriptions.get(n, {}).get("table")) or t.get("comment")
            if ttext:
                suffix += " COMMENT=" + _lit(ttext[:2000], target)
        create_blocks[n] = f"CREATE TABLE {qname(n)} (\n{body}\n){suffix};"
        stats["tables"] += 1
        tables_out.append({"name": n, "target_name": (tinfo[n]["schema"] + "." if tinfo[n]["schema"] else "") + tinfo[n]["name"], "columns": cols_out})

        if opts["include_comments"] and target in ("postgres", "mssql"):
            d = descriptions.get(n, {})
            ttext = d.get("table") or t.get("comment")
            if ttext:
                desc_blocks.append(_comment_sql(target, tinfo[n], None, ttext, namer))
            for c in t["columns"]:
                ctext = (d.get("columns", {}) or {}).get(c["name"]) or c.get("comment")
                if ctext:
                    desc_blocks.append(_comment_sql(target, tinfo[n], col_target[(n, c["name"])], ctext, namer))

    deps = {n: {r["ref_table"] for r in tables[n]["relations"] if r["ref_table"] in sel} for n in selected}
    order = _topo(selected, deps)

    # ---- advertencias generales ----
    notes = []
    if opts["include_fks"] is False:
        notes.append("Las claves foráneas están desactivadas en las opciones: no se crean.")
    if not any(c.get("prec") is not None or c.get("identity") for n in selected for c in tables[n]["columns"]) and source_engine in ("postgres", "mssql", "mysql"):
        notes.append("Este escaneo no trae precisión de decimales ni identidades: reescanea la conexión (versión 2.4 o posterior) para una traducción más fiel.")
    uses_identity = any(c.get("identity") for n in selected for c in tables[n]["columns"])
    if target == "postgres" and uses_identity and opts["include_identity"]:
        notes.append("Las columnas IDENTITY (GENERATED ... AS IDENTITY) requieren PostgreSQL 10 o superior; gen_random_uuid() requiere la versión 13 o superior.")
    for m in notes:
        warn("info", m)
    warn("info", "No se migran índices no únicos, restricciones CHECK, reglas ON DELETE/ON UPDATE (se usa la acción por defecto), vistas, procedimientos ni triggers. Tampoco los datos: eso es la fase 2.")

    # ---- script ----
    header = [
        "-- =====================================================================",
        f"-- Script de migración generado por Etch-DB-Mapper v{__version__}",
        f"-- Origen : {alias or 'esquema escaneado'} ({TARGETS.get(source_engine, source_engine or 'motor desconocido')})",
        f"-- Destino: {TARGETS[target]}",
        f"-- Fecha  : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "--",
        "-- Este script SOLO CREA objetos nuevos (esquema, tablas, claves). No contiene",
        "-- DROP, TRUNCATE, DELETE ni UPDATE y no usa IF NOT EXISTS: si algo ya existe",
        "-- en el destino fallará en lugar de pisarlo. Ejecútalo en una base NUEVA o vacía.",
        "-- Revisa las advertencias antes de ejecutarlo. No migra datos (fase 2).",
        "-- =====================================================================",
        "",
    ]
    body = []
    for s in schemas:
        stmt = f"CREATE SCHEMA {namer.q(s)};"
        body.append(stmt + ("\nGO" if target == "mssql" else ""))
    if schemas:
        body.append("")
    body.append("-- Tablas")
    for n in order:
        body += [create_blocks[n], ""]
    if fk_blocks:
        body += ["-- Claves foráneas"] + fk_blocks + [""]
    if desc_blocks:
        body += ["-- Descripciones"] + desc_blocks + [""]
    sql = "\n".join(header + body).rstrip() + "\n"

    stats["warnings"] = sum(1 for w in warnings if w["level"] == "warn")
    stats["errors"] = sum(1 for w in warnings if w["level"] == "error")
    stats["infos"] = sum(1 for w in warnings if w["level"] == "info")
    return {"sql": sql, "warnings": warnings, "stats": stats, "tables": tables_out, "target": target, "options": opts,
            "filename": re.sub(r"[^\w.\- ]+", "_", f"migracion_{alias or 'esquema'}_a_{target}").strip(" ._") + ".sql"}


def _bound_key_type(tsql: str, target: str):
    """SQL Server y MySQL no admiten tipos de texto 'sin límite' ni demasiado largos como clave (PK, UNIQUE,
    FK). Devuelve (tipo acotado | None si no hace falta, aviso)."""
    up = tsql.upper()
    m = re.match(r"^(N?)(VAR)?CHAR\((\d+)\)$", up)
    if target == "mssql":
        uni = up.startswith("N")
        if up in ("NVARCHAR(MAX)", "VARCHAR(MAX)"):
            new = "NVARCHAR(450)" if uni else "VARCHAR(900)"
            return new, f"Columna usada como clave: SQL Server no admite {tsql} en una clave; se limita a {new}."
        if m:
            n, limit = int(m.group(3)), (450 if uni else 900)
            if n > limit:
                new = f"{'N' if uni else ''}{'VAR' if m.group(2) else ''}CHAR({limit})"
                return new, f"Columna usada como clave: {tsql} supera el límite de 900 bytes de una clave de SQL Server; se limita a {new}."
    if target == "mysql":
        if up in ("LONGTEXT", "TEXT"):
            return "VARCHAR(255)", "Columna usada como clave: MySQL no admite TEXT en una clave sin longitud; se limita a VARCHAR(255)."
        if m and int(m.group(3)) > 768:
            return f"{'VAR' if m.group(2) else ''}CHAR(768)", f"Columna usada como clave: {tsql} supera el límite de índice de MySQL (utf8mb4); se limita a 768."
    return None, None


def _group_fks(t: dict, tables: dict) -> list:
    """Agrupa las relaciones de una tabla en claves foráneas (compuestas si coinciden con la PK compuesta del padre)."""
    by_ref = {}
    for r in t["relations"]:
        by_ref.setdefault(r["ref_table"], []).append(r)
    out = []
    for ref, rels in by_ref.items():
        parent_pk = [c["name"] for c in tables.get(ref, {}).get("columns", []) if c["pk"]] if ref in tables else []
        if len(rels) > 1 and len(parent_pk) == len(rels) and {r["ref_col"] for r in rels} == set(parent_pk):
            ordered = sorted(rels, key=lambda r: parent_pk.index(r["ref_col"]))
            out.append(([r["col"] for r in ordered], ref, [r["ref_col"] for r in ordered]))
        else:
            out += [([r["col"]], ref, [r["ref_col"]]) for r in rels]
    return out


def _comment_sql(target: str, info: dict, column, text: str, namer: _Namer) -> str:
    text = text[:4000]
    if target == "postgres":
        tname = (namer.q(info["schema"]) + "." if info["schema"] else "") + namer.q(info["name"])
        if column is None:
            return f"COMMENT ON TABLE {tname} IS {_lit(text, target)};"
        return f"COMMENT ON COLUMN {tname}.{namer.q(column)} IS {_lit(text, target)};"
    schema = info["schema"] or "dbo"
    base = (f"EXEC sp_addextendedproperty @name = N'MS_Description', @value = {_lit(text, target)}, "
            f"@level0type = N'SCHEMA', @level0name = {_lit(schema, target)}, @level1type = N'TABLE', @level1name = {_lit(info['name'], target)}")
    if column is not None:
        base += f", @level2type = N'COLUMN', @level2name = {_lit(column, target)}"
    return base + ";"
