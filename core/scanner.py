"""Lectura del esquema de una base de datos a través de pydal (DAL).

Diseño
------
* La conexión se abre con pydal, así que cualquier motor que pydal sepa
  abrir (y tenga su driver Python instalado) conecta.
* Leer el *esquema* es otra cosa: pydal no sabe hacer reflexión, así que
  cada familia de motores necesita un "lector". Hay un registro
  (`INTROSPECTORS`) y agregar un motor es escribir una función que
  devuelva el mismo formato crudo (ver `RawSchema`).
* Se hacen pocas consultas en TOTAL (4), no una por tabla: el patrón N+1
  anterior (3 consultas × cada tabla = 513 viajes de red para 171 tablas)
  era la causa de los escaneos de ~48 s.
* Ninguna consulta lleva parámetros ni concatena datos externos, así que
  no hay superficie de inyección ni diferencias de "paramstyle" entre
  drivers (el bug de `%s` vs `?` de la 1.5 desaparece por construcción).

Formato de salida de run_db_scan() -> ver docs/ARCHITECTURE.md.
"""
import re
import time
import importlib.util
from collections import Counter
from datetime import datetime

from pydal import DAL

from .uri import mask_uri  # noqa: F401  (se re-exporta para api.py)

# Prefijo de URI (pydal) -> (módulo Python requerido, cómo instalarlo).
# módulo None = no requiere driver externo (ej: sqlite, stdlib).
DRIVER_HINTS = {
    "mssql": ("pyodbc", "pip install pyodbc"),
    "postgres": ("psycopg2", "pip install psycopg2-binary"),
    "mysql": ("pymysql", "pip install pymysql"),
    "sqlite": (None, None),
    "oracle": ("cx_Oracle", "pip install cx_Oracle"),
    "firebird": ("fdb", "pip install fdb"),
    "db2": ("ibm_db", "pip install ibm_db"),
    "mongodb": ("pymongo", "pip install pymongo"),
}

SYSTEM_SCHEMAS = ("information_schema", "INFORMATION_SCHEMA", "pg_catalog", "pg_toast", "sys")

_TYPE_ALIASES = {
    "character varying": "varchar",
    "character": "char",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamptz",
    "time without time zone": "time",
    "time with time zone": "timetz",
    "double precision": "double",
}


class ScanError(Exception):
    """Error legible para el usuario (se muestra tal cual)."""


# ---------------------------------------------------------------- utilidades
_SECRET_PATTERNS = (
    (re.compile(r"(?i)(pwd|password|passwd)\s*=\s*[^;&\s]+"), lambda m: m.group(1) + "=••••"),
    (re.compile(r"(://[^:/@\s]+):[^@\s]+@"), lambda m: m.group(1) + ":••••@"),
)


def scrub_secrets(text: str) -> str:
    """Quita contraseñas que algún driver pudiera repetir dentro de un mensaje
    de error (cadenas de conexión tipo PWD=..., o URI con usuario:clave@)."""
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def summarize_error(exc) -> str:
    """pydal (y drivers como psycopg2/pyodbc) suelen devolver un traceback
    completo como mensaje. Nos quedamos con la última línea no vacía, que
    es la excepción real."""
    msg = scrub_secrets(str(exc).strip())
    for line in reversed(msg.splitlines()):
        if line.strip():
            return line.strip()
    return msg or exc.__class__.__name__


def detect_engine(uri):
    """'mssql4n://...' -> 'mssql'; None si no se reconoce."""
    match = re.match(r"^([a-zA-Z0-9]+)", uri or "")
    if not match:
        return None
    prefix = match.group(1).lower()
    for engine in DRIVER_HINTS:
        if prefix.startswith(engine):
            return engine
    return None


def check_driver_available(uri):
    """Mensaje claro si falta el driver Python del motor; None si está bien."""
    engine = detect_engine(uri)
    if not engine:
        return None
    module_name, install_hint = DRIVER_HINTS[engine]
    if module_name is None:
        return None
    if importlib.util.find_spec(module_name) is None:
        return f"Falta el driver '{module_name}' para conectar a {engine}. Instalalo con: {install_hint}"
    return None


def inspect_uri(uri: str) -> dict:
    """Chequeo barato (sin conectar) para la UI mientras se escribe la URI."""
    engine = detect_engine(uri)
    return {
        "engine": engine,
        # "native": lector propio; "generic": se intenta INFORMATION_SCHEMA estándar
        "reader": None if engine is None else ("native" if engine in INTROSPECTORS else "generic"),
        "driver_error": check_driver_available(uri),
    }


def _fmt_type(dtype, maxlen=None) -> str:
    dtype = _TYPE_ALIASES.get(str(dtype).lower(), str(dtype))
    if maxlen is None:
        return dtype
    try:
        n = int(maxlen)
    except (TypeError, ValueError):
        return dtype
    if n == -1:
        return f"{dtype}(max)"
    if 0 < n < 1_000_000:
        return f"{dtype}({n})"
    return dtype


def _schema_filter(engine, column):
    if engine == "mysql":
        return f"{column} = DATABASE()"
    quoted = ", ".join(f"'{s}'" for s in SYSTEM_SCHEMAS)
    return f"{column} NOT IN ({quoted})"


def _yes(value) -> bool:
    return str(value).strip().upper() in ("YES", "Y", "TRUE", "1")


# ------------------------------------------------------------- lectores crudos
# RawSchema = dict con:
#   tables  : [(schema, table)]
#   columns : [(schema, table, column, type, nullable: bool)]   (en orden)
#   pks     : [(schema, table, column)]
#   fks     : [(schema, table, column, ref_schema, ref_table, ref_column)]
def _introspect_information_schema(db, engine, emit):
    q = db.executesql
    flt = lambda col: _schema_filter(engine, col)  # noqa: E731

    emit("tables", "Leyendo tablas…", 15)
    tables = q(
        "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        f"WHERE TABLE_TYPE = 'BASE TABLE' AND {flt('TABLE_SCHEMA')}"
    )

    emit("columns", "Leyendo columnas…", 40)
    cols = q(
        "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
        f"FROM INFORMATION_SCHEMA.COLUMNS WHERE {flt('TABLE_SCHEMA')} "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
    )

    emit("keys", "Leyendo claves primarias…", 65)
    pks = q(
        "SELECT tc.TABLE_SCHEMA, tc.TABLE_NAME, ku.COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku "
        "  ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME "
        " AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA AND tc.TABLE_NAME = ku.TABLE_NAME "
        f"WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND {flt('tc.TABLE_SCHEMA')}"
    )

    emit("relations", "Leyendo relaciones…", 80)
    fks = _foreign_keys(db, engine, flt)
    return {
        "tables": [(r[0], r[1]) for r in tables],
        "columns": [(r[0], r[1], r[2], _fmt_type(r[3], r[4]), _yes(r[5])) for r in cols],
        "pks": [(r[0], r[1], r[2]) for r in pks],
        "fks": fks,
    }


def _foreign_keys(db, engine, flt):
    q = db.executesql
    if engine == "mssql":
        # Catálogo nativo: resuelve bien claves compuestas y las que apuntan
        # a índices únicos. Si el login no puede leer sys.*, se cae al genérico.
        try:
            rows = q(
                "SELECT OBJECT_SCHEMA_NAME(fkc.parent_object_id), OBJECT_NAME(fkc.parent_object_id), pc.name, "
                "       OBJECT_SCHEMA_NAME(fkc.referenced_object_id), OBJECT_NAME(fkc.referenced_object_id), rc.name "
                "FROM sys.foreign_key_columns fkc "
                "JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id "
                "JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id"
            )
            return [tuple(r) for r in rows]
        except Exception:
            pass
    # SQL Server no tiene POSITION_IN_UNIQUE_CONSTRAINT en su INFORMATION_SCHEMA
    # (solo llegamos acá si sys.* no estuvo disponible): el cruce por posición
    # se omite y las claves compuestas pueden repetir pares de columnas.
    position = "" if engine == "mssql" else " AND rel.ORDINAL_POSITION = kcu.POSITION_IN_UNIQUE_CONSTRAINT"
    rows = q(
        "SELECT kcu.TABLE_SCHEMA, kcu.TABLE_NAME, kcu.COLUMN_NAME, rel.TABLE_SCHEMA, rel.TABLE_NAME, rel.COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "  ON kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA AND kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE rel "
        "  ON rel.CONSTRAINT_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA AND rel.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME"
        f"{position} WHERE {flt('kcu.TABLE_SCHEMA')}"
    )
    return [tuple(r) for r in rows]


def _introspect_sqlite(db, engine, emit):
    q = db.executesql
    emit("tables", "Leyendo tablas…", 15)
    tables = q("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")

    emit("columns", "Leyendo columnas…", 40)
    cols = q(
        'SELECT m.name, p.name, p.type, p."notnull", p.pk FROM sqlite_master m '
        "JOIN pragma_table_info(m.name) p WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%' "
        "ORDER BY m.name, p.cid"
    )

    emit("keys", "Leyendo relaciones…", 70)
    fks = q(
        'SELECT m.name, f."from", f."table", f."to" FROM sqlite_master m '
        "JOIN pragma_foreign_key_list(m.name) f WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%'"
    )

    pk_cols = {}
    for table, _name, _type, _nn, pk in cols:
        if pk:
            pk_cols.setdefault(table, []).append(_name)
    resolved = []
    for table, col, ref_table, ref_col in fks:
        if not ref_col:  # "REFERENCES t" sin columna => apunta a la PK de t
            ref_col = (pk_cols.get(ref_table) or [None])[0]
        resolved.append(("main", table, col, "main", ref_table, ref_col))

    return {
        "tables": [("main", r[0]) for r in tables],
        "columns": [("main", t, c, (ty or "").lower() or "any", not (nn or pk)) for t, c, ty, nn, pk in cols],
        "pks": [("main", t, c) for t, c, _ty, _nn, pk in cols if pk],
        "fks": resolved,
    }


# Registro de lectores. Para agregar un motor: escribí una función con la
# misma firma que las de arriba, registrala acá y sumá un test en tests/.
INTROSPECTORS = {
    "mssql": _introspect_information_schema,
    "postgres": _introspect_information_schema,
    "mysql": _introspect_information_schema,
    "sqlite": _introspect_sqlite,
}


# ------------------------------------------------------------ armado del esquema
def build_schema(raw) -> dict:
    """Crudo -> {nombre_tabla: {...}} con columnas marcadas (pk/fk) y relaciones."""
    name_count = Counter(name for _schema, name in raw["tables"])

    def key_of(schema, name):
        # Si el mismo nombre existe en 2 esquemas, se distingue con prefijo.
        return name if name_count[name] == 1 else f"{schema}.{name}"

    tables = {}
    for schema, name in raw["tables"]:
        tables[key_of(schema, name)] = {"schema": schema, "name": name, "columns": [], "relations": []}

    pk_set = {(s, t, c) for s, t, c in raw["pks"]}
    for schema, table, col, ctype, nullable in raw["columns"]:
        entry = tables.get(key_of(schema, table))
        if entry is None:  # columna de una vista u objeto que no es tabla base
            continue
        is_pk = (schema, table, col) in pk_set
        entry["columns"].append({"name": col, "type": ctype, "null": bool(nullable) and not is_pk, "pk": is_pk, "fk": False})

    seen = set()
    for schema, table, col, rschema, rtable, rcol in raw["fks"]:
        src, dst = key_of(schema, table), key_of(rschema, rtable)
        if src not in tables or dst not in tables or (src, col, dst, rcol) in seen:
            continue
        seen.add((src, col, dst, rcol))
        tables[src]["relations"].append({"col": col, "ref_table": dst, "ref_col": rcol})

    return finalize_schema(tables)


def finalize_schema(tables: dict) -> dict:
    """Normaliza (acepta también el formato 1.x guardado en disco) y calcula
    las relaciones entrantes (`referenced_by`)."""
    out = {}
    for name, info in (tables or {}).items():
        relations = [
            {"col": r.get("col"), "ref_table": r.get("ref_table"), "ref_col": r.get("ref_col")}
            for r in info.get("relations", [])
        ]
        fk_cols = {r["col"] for r in relations}
        columns = []
        for c in info.get("columns", []):
            null = c.get("null")
            columns.append({
                "name": c.get("name"),
                "type": c.get("type", ""),
                "null": null in (True, "YES"),
                "pk": bool(c.get("pk", c.get("is_pk", False))),
                "fk": bool(c.get("fk")) or c.get("name") in fk_cols,
            })
        out[name] = {
            "schema": info.get("schema", ""),
            "name": info.get("name", name),
            "columns": columns,
            "relations": relations,
            "referenced_by": [],
        }
    for name, info in out.items():
        for r in info["relations"]:
            if r["ref_table"] in out:
                out[r["ref_table"]]["referenced_by"].append({"table": name, "col": r["col"], "ref_col": r["ref_col"]})
    return out


def compute_meta(tables: dict) -> dict:
    related = set()
    for name, info in tables.items():
        if info["relations"] or info["referenced_by"]:
            related.add(name)
    return {
        "table_count": len(tables),
        "column_count": sum(len(t["columns"]) for t in tables.values()),
        "relation_count": sum(len(t["relations"]) for t in tables.values()),
        "related_count": len(related),
        "orphan_count": len(tables) - len(related),
        "no_pk_count": sum(1 for t in tables.values() if not any(c["pk"] for c in t["columns"])),
    }


# ------------------------------------------------------------------ entrada
def _open_dal(uri, engine):
    # decode_credentials: usuario/clave pueden venir con %-codificación (el asistente
    # de conexión las codifica para que '@', ':' o '/' no rompan la URI).
    kwargs = {"migrate_enabled": False, "folder": None, "decode_credentials": True}
    if engine == "sqlite":
        import os
        path = uri.split("://", 1)[-1].split("?", 1)[0]
        if path != ":memory:" and not os.path.isabs(path) and not re.match(r"^[a-zA-Z]:", path):
            kwargs["folder"] = os.getcwd()
    return DAL(uri, **kwargs)


def test_connection(uri, timeout=5.0):
    """Prueba rápida (sin leer el esquema): driver instalado, red alcanzable y
    un `SELECT 1`. Devuelve {"ok": True, "seconds": s} o {"ok": False, "error": msg}."""
    import socket
    from .uri import target_of

    start = time.time()
    driver_error = check_driver_available(uri)
    if driver_error:
        return {"ok": False, "error": driver_error}
    engine = detect_engine(uri)
    target = target_of(uri)
    if target:   # falla rápido y claro si el servidor ni siquiera responde
        try:
            socket.create_connection(target, timeout=timeout).close()
        except OSError as e:
            return {"ok": False, "error": f"No se pudo alcanzar {target[0]}:{target[1]} ({e.strerror or e}). "
                                          "Revisá host, puerto, firewall o VPN."}
    db = None
    try:
        db = _open_dal(uri, engine)
        db.executesql("SELECT 1")
        return {"ok": True, "seconds": round(time.time() - start, 2)}
    except Exception as e:
        return {"ok": False, "error": summarize_error(e)}
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def run_db_scan(uri, progress=None):
    """Escanea la base y devuelve:
        {"status": "success", "data": {...}, "meta": {...}, "last_scan": str, "duration_sec": float}
      o {"status": "error", "message": str}

    `progress(phase, message, pct)` (opcional) se llama en cada fase:
    connect → tables → columns → keys → relations → build.
    """
    start = time.time()

    def emit(phase, message, pct=None):
        if progress:
            try:
                progress(phase, message, pct)
            except Exception:
                pass  # un fallo de la UI nunca debe romper el escaneo

    driver_error = check_driver_available(uri)
    if driver_error:
        return {"status": "error", "message": driver_error}

    engine = detect_engine(uri)
    db = None
    try:
        emit("connect", "Conectando…", 5)
        db = _open_dal(uri, engine)
        introspect = INTROSPECTORS.get(engine, _introspect_information_schema)
        try:
            raw = introspect(db, engine, emit)
        except Exception as e:
            if engine in INTROSPECTORS:
                raise
            raise ScanError(
                f"Conectó, pero el motor '{engine or 'desconocido'}' no expone un INFORMATION_SCHEMA estándar "
                f"y todavía no tiene lector de esquema propio ({summarize_error(e)}). "
                "Ver docs/ARCHITECTURE.md para agregar uno."
            )
        emit("build", "Armando el esquema…", 92)
        tables = build_schema(raw)
        return {
            "status": "success",
            "data": tables,
            "meta": {**compute_meta(tables), "engine": engine},
            "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": round(time.time() - start, 2),
        }
    except ScanError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": summarize_error(e)}
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
