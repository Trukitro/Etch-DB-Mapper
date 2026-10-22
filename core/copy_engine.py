"""Migración, fase 2: copiar los datos de una base a otra.

Reglas de seguridad (ver docs/MIGRATION_PLAN.md):

1. **El origen es de solo lectura.** En PostgreSQL (transacción REPEATABLE READ READ ONLY, que además da una
   foto consistente), MySQL (SESSION TRANSACTION READ ONLY) y SQLite (PRAGMA query_only) lo impone la propia base.
   SQL Server no tiene un modo de sesión de solo lectura: ahí lo impone la app (solo emite SELECT y rechaza
   cualquier otra sentencia) y se recomienda usar un login de solo lectura.
2. **El destino debe estar limpio**: sin tablas de usuario, o —si las tiene— con esquema/prefijo nuevos y sin
   ninguna colisión de nombres. Si no se cumple, no se escribe nada.
3. **Nunca se borra ni se sobrescribe**: no hay DROP, TRUNCATE, DELETE ni UPDATE sobre lo existente; las tablas se
   crean con CREATE TABLE (falla si existen).
4. Todo o nada por tabla (transacción); ante el primer error se detiene y se informa qué terminó y qué no.
5. Plan previo (sin escribir), simulacro (lee y convierte sin escribir) y verificación de conteos al final.
6. Nunca se registran valores de las tablas (solo nombres y conteos).
"""
import json
import re
import struct
import threading
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import Decimal

from .joins import _qualified, quote_ident
from .migrate import DEFAULT_SCHEMAS, TARGETS, generate_ddl
from .scanner import _open_dal, _schema_filter, scrub_secrets, summarize_error

BATCH = 1000
SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.I)


class CopyError(Exception):
    """Error esperable con mensaje claro para el usuario."""


class Cancelled(Exception):
    pass


# ------------------------------------------------------------------ origen
def _mssql_datetimeoffset(raw):
    """pyodbc entrega DATETIMEOFFSET como bytes: se decodifica a datetime con zona."""
    y, mo, d, h, mi, s, ns, tzh, tzm = struct.unpack("<6hI2h", raw)
    return datetime(y, mo, d, h, mi, s, ns // 1000, timezone(timedelta(hours=tzh, minutes=tzm)))


class SourceReader:
    """Conexión de SOLO LECTURA al origen."""

    def __init__(self, uri: str, engine: str):
        self.engine = engine
        self.db = _open_dal(uri, engine)
        self.conn = self.db._adapter.connection
        self.read_only_by = "app"
        self._make_read_only()

    def _make_read_only(self):
        e = self.engine
        try:
            if e == "postgres":
                self.conn.rollback()
                self.conn.set_session(isolation_level="REPEATABLE READ", readonly=True)   # foto consistente y sin escrituras
                self.read_only_by = "database"
            elif e == "mysql":
                cur = self.conn.cursor()
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                cur.close()
                self.read_only_by = "database"
            elif e == "sqlite":
                cur = self.conn.cursor()
                cur.execute("PRAGMA query_only = ON")
                cur.close()
                self.read_only_by = "database"
            elif e == "mssql":
                self.conn.add_output_converter(-155, _mssql_datetimeoffset)
        except Exception as ex:
            raise CopyError("No se pudo poner el origen en modo solo lectura: " + summarize_error(ex))

    @staticmethod
    def _guard(sql: str):
        if not SELECT_ONLY.match(sql) or ";" in sql.strip().rstrip(";"):
            raise CopyError("Sentencia rechazada: el origen solo admite SELECT.")

    def count(self, qname: str) -> int:
        sql = f"SELECT COUNT(*) FROM {qname}"
        self._guard(sql)
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            return int(cur.fetchone()[0])
        finally:
            cur.close()

    def _cursor(self):
        if self.engine == "postgres":
            return self.conn.cursor(name="etch_copy_%d" % int(time.time() * 1000))   # cursor del servidor: no carga todo en memoria
        if self.engine == "mysql":
            import pymysql.cursors
            return self.conn.cursor(pymysql.cursors.SSCursor)
        return self.conn.cursor()

    def stream(self, sql: str, batch: int = BATCH):
        self._guard(sql)
        cur = self._cursor()
        try:
            cur.execute(sql)
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                yield rows
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def close(self):
        try:
            self.conn.rollback()
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass


# ----------------------------------------------------------------- destino
class TargetWriter:
    def __init__(self, uri: str, engine: str):
        self.engine = engine
        self.db = _open_dal(uri, engine)
        self.conn = self.db._adapter.connection
        style = getattr(self.db._adapter.driver, "paramstyle", "qmark")
        self.ph = "%s" if style in ("format", "pyformat") else "?"
        self.cur = self.conn.cursor()

    def execute(self, sql: str, params=None):
        self.cur.execute(sql) if params is None else self.cur.execute(sql, params)

    def executemany(self, sql: str, rows: list):
        if self.engine == "postgres":
            from psycopg2.extras import execute_batch
            execute_batch(self.cur, sql, rows, page_size=500)
        else:
            self.cur.executemany(sql, rows)

    def scalar(self, sql: str):
        self.cur.execute(sql)
        return self.cur.fetchone()[0]

    def commit(self):
        self.conn.commit()

    def rollback(self):
        try:
            self.conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self.cur.close()
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass


def inspect_target(db, engine: str) -> dict:
    """Qué hay ya en el destino (solo lectura de catálogo): tablas de usuario y esquemas."""
    q = db.executesql
    if engine == "sqlite":
        tables = [("main", r[0]) for r in q("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        return {"tables": tables, "schemas": []}
    flt = lambda col: _schema_filter(engine, col)  # noqa: E731
    tables = [(r[0], r[1]) for r in q("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                                      f"WHERE TABLE_TYPE = 'BASE TABLE' AND {flt('TABLE_SCHEMA')}")]
    schemas = []
    if engine in ("postgres", "mssql"):
        schemas = [r[0] for r in q(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE {flt('SCHEMA_NAME')}")]
    return {"tables": tables, "schemas": schemas}


def _norm_name(schema, name) -> str:
    s = (schema or "").strip().lower()
    return (name or "").lower() if s in DEFAULT_SCHEMAS else f"{s}.{(name or '').lower()}"


def target_blockers(dst_uri: str, dst_engine: str, ddl: dict) -> tuple:
    """Comprueba el destino SIN escribir. -> (bloqueos [str], tablas existentes [str])."""
    db = _open_dal(dst_uri, dst_engine)
    try:
        found = inspect_target(db, dst_engine)
    finally:
        try:
            db.close()
        except Exception:
            pass
    existing = [f"{s}.{t}" if (s or "").lower() not in DEFAULT_SCHEMAS else t for s, t in found["tables"]]
    blockers = []
    opts = ddl["options"]
    planned = {}
    for t in ddl["tables"]:
        schema, _, name = t["target_name"].rpartition(".")
        planned[_norm_name(schema, name)] = t["target_name"]
    existing_norm = {_norm_name(s, t): (f"{s}.{t}" if (s or "").lower() not in DEFAULT_SCHEMAS else t) for s, t in found["tables"]}
    collisions = sorted(planned[k] for k in planned if k in existing_norm)
    if collisions:
        blockers.append("Estas tablas ya existen en el destino y no se tocan: " + ", ".join(collisions[:10]) + (" …" if len(collisions) > 10 else "") +
                        ". Elige un esquema nuevo o un prefijo distinto.")
    if existing and not collisions and not (opts.get("target_schema") or opts.get("table_prefix")):
        blockers.append(f"El destino ya tiene {len(existing)} tablas ({', '.join(existing[:5])}{' …' if len(existing) > 5 else ''}). "
                        "Se exige un destino vacío, o un esquema/prefijo nuevo para no mezclar.")
    ts = (opts.get("target_schema") or "").lower()
    if ts and ts in {s.lower() for s in found["schemas"]}:
        blockers.append(f"El esquema «{opts['target_schema']}» ya existe en el destino: elige uno nuevo.")
    return blockers, existing


# ------------------------------------------------------------- conversiones
def _utc_naive(v: datetime) -> datetime:
    return v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v


def make_converter(kind: str, dst: str, column: str):
    """Función que lleva un valor leído del origen al formato que acepta el destino (según el tipo de origen)."""

    def fail(msg):
        raise CopyError(f"Columna «{column}»: {msg}")

    def text(v):
        if isinstance(v, (dict, list, tuple)):
            return json.dumps(v, ensure_ascii=False, default=str)
        if isinstance(v, (bytes, bytearray, memoryview)):
            return bytes(v).decode("utf-8", "replace")
        v = v if isinstance(v, str) else str(v)
        if dst == "postgres" and "\x00" in v:
            fail("contiene caracteres NUL (0x00), que PostgreSQL no admite en texto.")
        return v

    def number(v):
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, Decimal) and dst == "sqlite":
            return str(v)
        return v

    def boolean(v):
        return bool(v) if dst == "postgres" else int(bool(v))

    def binary(v):
        return bytes(v) if isinstance(v, (memoryview, bytearray)) else v

    def dt(v):
        if isinstance(v, str):
            return v
        if isinstance(v, date) and not isinstance(v, datetime):
            v = datetime(v.year, v.month, v.day)
        if dst == "sqlite":
            return _utc_naive(v).isoformat(sep=" ")
        if dst == "mssql" and kind == "datetimetz":
            return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat(sep=" ")
        if dst == "postgres" and kind == "datetimetz":
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return _utc_naive(v)

    def day(v):
        if isinstance(v, datetime):
            v = v.date()
        return v.isoformat() if (dst == "sqlite" and isinstance(v, date)) else v

    def clock(v):
        if isinstance(v, timedelta):
            secs = int(v.total_seconds())
            return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"
        if isinstance(v, dtime) and dst == "sqlite":
            return v.isoformat()
        return v

    fn = {"bool": boolean, "int": number, "bigint": number, "smallint": number, "tinyint": number, "decimal": number, "money": number,
          "real": lambda v: float(v), "double": lambda v: float(v), "binary": binary, "rowversion": binary,
          "datetime": dt, "datetimetz": dt, "date": day, "time": clock, "uuid": lambda v: str(v),
          "json": lambda v: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)}.get(kind, text)

    def convert(v):
        return None if v is None else fn(v)
    return convert


# ------------------------------------------------------------------ copia
def _insert_columns(tinfo: dict, dst: str) -> list:
    """Columnas que se copian: ROWVERSION de SQL Server se genera solo y no admite valores."""
    return [c for c in tinfo["columns"] if not (c["target_type"].upper() == "ROWVERSION" and dst == "mssql")]


def run_copy(ddl: dict, tables: dict, src_engine: str, src_uri: str, dst_engine: str, dst_uri: str, progress, cancel: threading.Event,
             dry_run: bool = False, source_counts: dict = None) -> dict:
    """Ejecuta (o simula) la copia. Devuelve un informe; nunca lanza por errores esperables."""
    t0 = time.time()
    counts = source_counts or {}
    report = {"ok": False, "dry_run": dry_run, "cancelled": False, "tables": [], "errors": [], "warnings": [], "rows_copied": 0,
              "rows_total": sum(counts.values()), "seconds": 0.0}
    src = dst = None
    by_name = {t["name"]: t for t in ddl["tables"]}
    create_sql = {s["table"]: s["sql"] for s in ddl["statements"] if s["kind"] == "table"}
    try:
        src = SourceReader(src_uri, src_engine)
        if not dry_run:
            dst = TargetWriter(dst_uri, dst_engine)
            for st in (s for s in ddl["statements"] if s["kind"] == "schema"):
                dst.execute(st["sql"])
                dst.commit()
        order = ddl["order"]
        for idx, name in enumerate(order):
            if cancel.is_set():
                raise Cancelled()
            tinfo = by_name[name]
            entry = {"name": name, "target_name": tinfo["target_name"], "rows_source": counts.get(name), "rows_copied": 0, "rows_target": None, "ok": False}
            report["tables"].append(entry)
            progress({"phase": "table", "table": name, "index": idx, "tables_total": len(order), "rows_done": 0, "rows_total": counts.get(name, 0),
                      "rows_copied_total": report["rows_copied"], "rows_all": report.get("rows_total", 0)})
            _copy_table(src, dst, src_engine, dst_engine, tables[name], tinfo, create_sql[name], entry, dry_run, cancel, progress, idx, len(order), report)
            entry["ok"] = True
        if not dry_run:
            _finish(dst, ddl, report)
        report["ok"] = not report["errors"]
    except Cancelled:
        report["cancelled"] = True
        report["errors"].append("Copia cancelada. La tabla en curso se revirtió; las ya terminadas quedan en el destino.")
    except CopyError as e:
        report["errors"].append(str(e))
    except Exception as e:   # error del driver / de la base
        report["errors"].append(summarize_error(e))
    finally:
        _note_leftover(report, dst_engine, dry_run)
        for c in (src, dst):
            if c is not None:
                c.close()
        report["seconds"] = round(time.time() - t0, 2)
    return report


def _note_leftover(report, dst_engine, dry_run):
    """MySQL y SQLite no revierten CREATE TABLE: si la última tabla falló o se canceló queda creada pero vacía."""
    if dry_run or dst_engine not in ("mysql", "sqlite") or not report["tables"]:
        return
    last = report["tables"][-1]
    if last.get("created") and not last["ok"]:
        report["warnings"].append(f"La tabla «{last['name']}» quedó creada pero vacía (este motor no revierte CREATE TABLE). "
                                  "La app nunca borra nada: elimínala a mano si vas a repetir la copia.")


def _copy_table(src, dst, src_engine, dst_engine, stable, tinfo, create_sql, entry, dry_run, cancel, progress, idx, total, report):
    name = tinfo["name"]
    if cancel.is_set():
        raise Cancelled()                              # antes de crear nada
    cols = _insert_columns(tinfo, dst_engine)
    select = "SELECT " + ", ".join(quote_ident(src_engine, c["name"]) for c in cols) + " FROM " + _qualified(src_engine, {name: stable}, name)
    convs = [make_converter(c["source_kind"], dst_engine, c["name"]) for c in cols]
    identity = [c for c in tinfo["columns"] if c.get("identity")]
    insert = None
    if not dry_run:
        insert = f"INSERT INTO {tinfo['qname']} ({', '.join(c['qname'] for c in cols)}) VALUES ({', '.join([dst.ph] * len(cols))})"
        dst.execute(create_sql)                        # CREATE TABLE a secas: si existe, falla (no pisa nada)
        entry["created"] = True
        if dst_engine == "mssql" and identity:
            dst.execute(f"SET IDENTITY_INSERT {tinfo['qname']} ON")
    done, last = 0, 0.0
    gen = src.stream(select)
    try:
        for batch in gen:
            if cancel.is_set():
                raise Cancelled()
            out = []
            for row in batch:
                try:
                    out.append(tuple(cv(v) for cv, v in zip(convs, row)))
                except CopyError as e:
                    raise CopyError(f"Tabla «{name}», fila {done + len(out) + 1}: {e}")
            if not dry_run:
                dst.executemany(insert, out)
            done += len(batch)
            entry["rows_copied"] = done
            now = time.time()
            if now - last > 0.25:
                last = now
                progress({"phase": "table", "table": name, "index": idx, "tables_total": total, "rows_done": done, "rows_total": entry["rows_source"] or 0,
                          "rows_copied_total": report["rows_copied"] + done, "rows_all": report.get("rows_total", 0)})
        if not dry_run:
            if dst_engine == "mssql" and identity:
                dst.execute(f"SET IDENTITY_INSERT {tinfo['qname']} OFF")
            dst.commit()
            if dst_engine == "postgres":
                for c in identity:
                    dst.execute(f"SELECT setval(pg_get_serial_sequence('{tinfo['qname'].replace(chr(39), chr(39) * 2)}', "
                                f"'{c['target_name'].replace(chr(39), chr(39) * 2)}'), COALESCE(MAX({c['qname']}), 1), MAX({c['qname']}) IS NOT NULL) "
                                f"FROM {tinfo['qname']}")
                dst.commit()
            entry["rows_target"] = int(dst.scalar(f"SELECT COUNT(*) FROM {tinfo['qname']}"))
            if entry["rows_target"] != done:
                raise CopyError(f"Verificación fallida en «{name}»: se copiaron {done} filas pero el destino tiene {entry['rows_target']}.")
        if entry["rows_source"] is not None and entry["rows_source"] != done:
            report["warnings"].append(f"«{name}»: el origen tenía {entry['rows_source']} filas al revisar y se leyeron {done} (¿hubo escrituras mientras se copiaba?).")
    except BaseException:
        if not dry_run:
            dst.rollback()          # revierte las filas de esta tabla (y su CREATE donde el motor lo permite)
        raise
    finally:
        gen.close()
    report["rows_copied"] += done


def _finish(dst, ddl, report):
    """Después de cargar los datos: claves foráneas y descripciones (un fallo aquí se informa, no borra nada)."""
    for st in (s for s in ddl["statements"] if s["kind"] in ("fk", "comment")):
        try:
            dst.execute(st["sql"])
            dst.commit()
        except Exception as e:
            dst.rollback()
            what = "clave foránea" if st["kind"] == "fk" else "descripción"
            report["warnings"].append(f"No se pudo crear una {what} en «{st['table']}»: {scrub_secrets(summarize_error(e))[:200]}")


# ---------------------------------------------------------------- plan previo
def build_plan(tables: dict, src_engine: str, src_uri: str, dst_engine: str, dst_uri: str, options: dict, alias: str, descriptions: dict,
               same_connection: bool = False) -> dict:
    """Plan previo SIN escribir nada: script, comprobaciones del destino y conteos del origen."""
    if dst_engine not in TARGETS:
        raise ValueError("El motor del destino no está soportado para copiar datos.")
    ddl = generate_ddl(tables, src_engine, dst_engine, options, alias=alias, descriptions=descriptions)
    blockers = []
    if same_connection:
        blockers.append("El origen y el destino son la misma conexión.")
    if ddl["stats"]["errors"]:
        blockers.append(f"El script de creación tiene {ddl['stats']['errors']} errores (nombres repetidos o demasiado largos): corrígelos con un prefijo o esquema distinto.")
    existing = []
    if not same_connection:
        try:
            tb, existing = target_blockers(dst_uri, dst_engine, ddl)
            blockers += tb
        except Exception as e:
            blockers.append("No se pudo revisar el destino: " + scrub_secrets(summarize_error(e)))
    counts, read_only_by = {}, "app"
    try:
        src = SourceReader(src_uri, src_engine)
        try:
            read_only_by = src.read_only_by
            for name in ddl["order"]:
                counts[name] = src.count(_qualified(src_engine, tables, name))
        finally:
            src.close()
    except CopyError as e:
        blockers.append(str(e))
    except Exception as e:
        blockers.append("No se pudo leer el origen: " + scrub_secrets(summarize_error(e)))
    return {"ddl": ddl, "blockers": blockers, "existing": existing, "counts": counts, "read_only_by": read_only_by}
