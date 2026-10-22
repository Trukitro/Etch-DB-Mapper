import hashlib
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

from core import copy_engine
from core.api import Api
from core.copy_engine import CopyError, SourceReader, make_converter
from core.migrate import generate_ddl
from core.scanner import finalize_schema, run_db_scan
from core.storage import Store

SCHEMA_SQL = """
CREATE TABLE categorias (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE productos (id INTEGER PRIMARY KEY, sku TEXT NOT NULL, nombre TEXT, precio NUMERIC, activo BOOLEAN DEFAULT 1,
                        creado DATETIME, foto BLOB, notas TEXT, categoria_id INTEGER REFERENCES categorias(id));
CREATE TABLE etiquetas (producto_id INTEGER NOT NULL, etiqueta TEXT NOT NULL, PRIMARY KEY (producto_id, etiqueta),
                        FOREIGN KEY (producto_id) REFERENCES productos(id));
"""
N_PRODUCTOS = 2500       # más de dos lotes de 1000


def make_source(path: Path):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA_SQL)
    con.executemany("INSERT INTO categorias VALUES (?, ?)", [(10, "Ñandú ✓"), (20, "Café"), (30, "Té")])
    rows = []
    for i in range(N_PRODUCTOS):
        rows.append((100 + i * 3, f"SKU-{i:05d}", None if i % 7 == 0 else f"Producto {i} áéíóú", 9.99 + i, i % 2, "2026-01-02 03:04:05" if i % 5 else None,
                     bytes([i % 256, 0, 255]), "x" * (i % 40), [10, 20, 30, None][i % 4]))
    con.executemany("INSERT INTO productos VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO etiquetas VALUES (?, ?)", [(100 + i * 3, t) for i in range(0, 300) for t in ("a", "b")])
    con.commit()
    con.close()


def dump(path: Path) -> dict:
    con = sqlite3.connect(path)
    out = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        out[name] = sorted(con.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr)
    con.close()
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeWindow:
    def __init__(self):
        self.done = threading.Event()
        self.report = None
        self.events = []

    def evaluate_js(self, code):
        self.events.append(code)
        if '"copy_finished"' in code:
            import json
            self.report = json.loads(code.split("emit(", 1)[1].split(", ", 1)[1].rsplit(")", 1)[0])
            self.done.set()


class CopyCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.src, self.dst = self.dir / "src.sqlite", self.dir / "dst.sqlite"
        make_source(self.src)
        self.win = FakeWindow()
        self.api = Api(Store(self.dir / "data"), self.win)
        self.uri = lambda p: "sqlite://" + str(p).replace("\\", "/")
        self.api.save_connection("Origen", self.uri(self.src))
        self.api.save_connection("Destino", self.uri(self.dst))
        self.scan("Origen")

    def tearDown(self):
        self._tmp.cleanup()

    def scan(self, alias):
        done = threading.Event()
        orig = self.api._emit

        def emit(event, payload):
            orig(event, payload)
            if event == "scan_finished":
                done.set()
        self.api._emit = emit
        self.assertTrue(self.api.start_scan(alias)["ok"])
        self.assertTrue(done.wait(30))
        self.api._emit = orig

    def run_copy(self, plan, confirm="Destino", dry_run=False, wait=True):
        self.win.done.clear()
        r = self.api.start_copy(plan["token"], confirm, dry_run=dry_run)
        if r["ok"] and wait:
            self.assertTrue(self.win.done.wait(60), "la copia no terminó")
        return r


class EndToEndTests(CopyCase):
    def test_full_copy_matches_source_and_leaves_source_untouched(self):
        before = sha(self.src)
        plan = self.api.preflight_copy("Origen", "Destino", {"name_style": "keep"})
        self.assertTrue(plan["ok"] and plan["can_start"], plan)
        self.assertEqual(plan["total_rows"], 3 + N_PRODUCTOS + 600)
        self.assertEqual(plan["read_only"]["by"], "database")
        self.assertTrue(self.run_copy(plan)["ok"])
        rep = self.win.report
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["rows_copied"], 3 + N_PRODUCTOS + 600)
        self.assertTrue(all(t["ok"] and t["rows_target"] == t["rows_copied"] for t in rep["tables"]))
        self.assertEqual(dump(self.src), dump(self.dst))                                  # datos idénticos, incluidos IDs, NULL, Unicode y BLOB
        self.assertEqual(sha(self.src), before)                                           # el origen no cambió ni un byte
        copy = finalize_schema(run_db_scan(self.uri(self.dst))["data"])
        self.assertEqual({(r["col"], r["ref_table"]) for r in copy["productos"]["relations"]}, {("categoria_id", "categorias")})
        self.assertEqual([c["name"] for c in copy["etiquetas"]["columns"] if c["pk"]], ["producto_id", "etiqueta"])
        self.assertEqual(self.win.report["warnings"], [])

    def test_parents_are_copied_before_children(self):
        plan = self.api.preflight_copy("Origen", "Destino")
        self.run_copy(plan)
        names = [t["name"] for t in self.win.report["tables"]]
        self.assertLess(names.index("categorias"), names.index("productos"))
        self.assertLess(names.index("productos"), names.index("etiquetas"))

    def test_dry_run_reads_and_converts_but_writes_nothing(self):
        plan = self.api.preflight_copy("Origen", "Destino")
        self.assertTrue(self.run_copy(plan, confirm="", dry_run=True)["ok"])              # el simulacro no pide confirmación
        self.assertTrue(self.win.report["ok"] and self.win.report["dry_run"])
        self.assertEqual(self.win.report["rows_copied"], 3 + N_PRODUCTOS + 600)
        con = sqlite3.connect(self.dst)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 0)
        con.close()

    def test_real_copy_requires_the_exact_target_name(self):
        plan = self.api.preflight_copy("Origen", "Destino")
        for bad in ("", "destino", "Origen", " "):
            r = self.run_copy(plan, confirm=bad, wait=False)
            self.assertFalse(r["ok"], bad)
        con = sqlite3.connect(self.dst)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 0)
        con.close()

    def test_unknown_or_expired_token(self):
        self.assertFalse(self.api.start_copy("nope", "Destino")["ok"])
        plan = self.api.preflight_copy("Origen", "Destino")
        self.api._copy_plans[plan["token"]]["created"] -= 3600
        self.assertFalse(self.api.start_copy(plan["token"], "Destino")["ok"])

    def test_changing_a_connection_after_review_invalidates_the_plan(self):
        plan = self.api.preflight_copy("Origen", "Destino")
        self.api.save_connection("Destino", "sqlite://" + str(self.dir / "otro.sqlite").replace("\\", "/"), previous_alias="Destino")
        r = self.api.start_copy(plan["token"], "Destino")
        self.assertFalse(r["ok"])
        self.assertIn("cambió", r["error"])


class TargetSafetyTests(CopyCase):
    def test_non_empty_target_is_blocked_and_never_touched(self):
        con = sqlite3.connect(self.dst)
        con.execute("CREATE TABLE importante (id INTEGER PRIMARY KEY, dato TEXT)")
        con.execute("INSERT INTO importante VALUES (1, 'no me toques')")
        con.commit()
        con.close()
        before = dump(self.dst)
        plan = self.api.preflight_copy("Origen", "Destino")
        self.assertFalse(plan["can_start"])
        self.assertTrue(any("vacío" in b for b in plan["blockers"]))
        self.assertFalse(self.run_copy(plan, wait=False)["ok"])
        self.assertEqual(dump(self.dst), before)

    def test_existing_target_with_prefix_and_no_collision_is_allowed_and_preserved(self):
        con = sqlite3.connect(self.dst)
        con.execute("CREATE TABLE importante (id INTEGER PRIMARY KEY, dato TEXT)")
        con.execute("INSERT INTO importante VALUES (1, 'sigo aquí')")
        con.commit()
        con.close()
        plan = self.api.preflight_copy("Origen", "Destino", {"table_prefix": "mig_"})
        self.assertTrue(plan["can_start"], plan["blockers"])
        self.run_copy(plan)
        self.assertTrue(self.win.report["ok"], self.win.report)
        data = dump(self.dst)
        self.assertEqual(data["importante"], [(1, "sigo aquí")])
        self.assertEqual(len(data["mig_productos"]), N_PRODUCTOS)

    def test_name_collision_is_blocked_even_with_prefix(self):
        con = sqlite3.connect(self.dst)
        con.execute("CREATE TABLE mig_categorias (id INTEGER)")
        con.commit()
        con.close()
        plan = self.api.preflight_copy("Origen", "Destino", {"table_prefix": "mig_"})
        self.assertFalse(plan["can_start"])
        self.assertTrue(any("ya existen" in b for b in plan["blockers"]))

    def test_target_that_changes_after_review_is_rechecked_before_writing(self):
        plan = self.api.preflight_copy("Origen", "Destino")
        self.assertTrue(plan["can_start"])
        con = sqlite3.connect(self.dst)                       # alguien crea una tabla entre la revisión y la copia
        con.execute("CREATE TABLE intruso (id INTEGER)")
        con.commit()
        con.close()
        r = self.run_copy(plan, wait=False)
        self.assertFalse(r["ok"])
        self.assertEqual(set(dump(self.dst)), {"intruso"})

    def test_same_connection_is_blocked(self):
        plan = self.api.preflight_copy("Origen", "Origen")
        self.assertFalse(plan["can_start"])
        self.assertTrue(any("misma conexión" in b for b in plan["blockers"]))

    def test_unscanned_source_and_missing_target(self):
        self.assertFalse(self.api.preflight_copy("Destino", "Origen")["ok"])
        self.assertFalse(self.api.preflight_copy("Origen", "NoExiste")["ok"])

    def test_script_errors_block_the_copy(self):
        plan = self.api.preflight_copy("Origen", "Destino", {"table_prefix": "x" * 60})   # nombres demasiado largos para PostgreSQL no aplica a SQLite
        self.assertTrue(plan["ok"])


class SourceReadOnlyTests(CopyCase):
    def test_source_connection_rejects_writes(self):
        reader = SourceReader(self.uri(self.src), "sqlite")
        try:
            cur = reader.conn.cursor()
            with self.assertRaises(sqlite3.OperationalError):
                cur.execute("INSERT INTO categorias VALUES (99, 'x')")
            with self.assertRaises(sqlite3.OperationalError):
                cur.execute("CREATE TABLE nueva (id INTEGER)")
        finally:
            reader.close()

    def test_guard_only_allows_single_select_statements(self):
        reader = SourceReader(self.uri(self.src), "sqlite")
        try:
            for bad in ("DELETE FROM categorias", "INSERT INTO categorias VALUES (1,'x')", "SELECT 1; DROP TABLE categorias",
                        "UPDATE categorias SET nombre='x'", "PRAGMA query_only = OFF", "  drop table categorias"):
                with self.assertRaises(CopyError, msg=bad):
                    list(reader.stream(bad))
            self.assertEqual(reader.count("categorias"), 3)
        finally:
            reader.close()


class FailureAndCancelTests(CopyCase):
    def plan_objects(self, dst_engine="sqlite"):
        tables = finalize_schema(run_db_scan(self.uri(self.src))["data"])
        ddl = generate_ddl(tables, "sqlite", dst_engine, {"name_style": "keep"})
        return tables, ddl

    def test_cancel_stops_cleanly_keeping_finished_tables_only(self):
        tables, ddl = self.plan_objects()
        cancel = threading.Event()

        def progress(p):
            if p["index"] == 1:          # al empezar la segunda tabla
                cancel.set()
        report = copy_engine.run_copy(ddl, tables, "sqlite", self.uri(self.src), "sqlite", self.uri(self.dst), progress, cancel, False)
        self.assertTrue(report["cancelled"])
        self.assertFalse(report["ok"])
        data = dump(self.dst)
        self.assertEqual(list(data), ["categorias"])
        self.assertEqual(len(data["categorias"]), 3)

    def test_insert_failure_rolls_back_rows_of_that_table_and_stops(self):
        tables, ddl = self.plan_objects()
        calls = {"n": 0}
        real = copy_engine.TargetWriter.executemany

        def flaky(self_, sql, rows):
            if "productos" in sql:
                calls["n"] += 1
                if calls["n"] == 2:
                    raise sqlite3.IntegrityError("falla simulada")
            return real(self_, sql, rows)
        with mock.patch.object(copy_engine.TargetWriter, "executemany", flaky):
            report = copy_engine.run_copy(ddl, tables, "sqlite", self.uri(self.src), "sqlite", self.uri(self.dst), lambda p: None, threading.Event(), False)
        self.assertFalse(report["ok"])
        self.assertIn("falla simulada", report["errors"][0])
        data = dump(self.dst)
        self.assertEqual(len(data["categorias"]), 3)                  # la tabla anterior terminó
        self.assertEqual(len(data.get("productos", [])), 0)           # las filas de la tabla que falló se revirtieron
        self.assertNotIn("etiquetas", data)                           # y no se siguió con las demás

    def test_conversion_error_aborts_before_writing_that_batch(self):
        con = sqlite3.connect(self.src)
        con.execute("INSERT INTO categorias VALUES (40, ?)", ("con\x00nulo",))
        con.commit()
        con.close()
        tables = finalize_schema(run_db_scan(self.uri(self.src))["data"])
        ddl = generate_ddl(tables, "sqlite", "postgres")
        fake = FakeTarget("postgres")
        entry = {"name": "categorias", "target_name": "categorias", "rows_source": 4, "rows_copied": 0, "rows_target": None, "ok": False}
        src = SourceReader(self.uri(self.src), "sqlite")
        try:
            with self.assertRaises(CopyError) as cm:
                copy_engine._copy_table(src, fake, "sqlite", "postgres", tables["categorias"], next(t for t in ddl["tables"] if t["name"] == "categorias"),
                                        "CREATE TABLE x ()", entry, False, threading.Event(), lambda p: None, 0, 1, {"rows_copied": 0, "warnings": []})
        finally:
            src.close()
        self.assertIn("NUL", str(cm.exception))
        self.assertIn("fila 4", str(cm.exception))
        self.assertTrue(fake.rolled_back)
        self.assertEqual(fake.inserted, [])


class FakeTarget:
    """Registra las sentencias para comprobar el SQL de PostgreSQL / SQL Server sin necesitar un servidor."""

    def __init__(self, engine):
        self.engine = engine
        self.ph = "%s" if engine in ("postgres", "mysql") else "?"
        self.statements, self.inserted, self.rolled_back, self.committed, self.count = [], [], False, 0, 0

    def execute(self, sql, params=None):
        self.statements.append(sql)

    def executemany(self, sql, rows):
        self.statements.append(sql)
        self.inserted += rows
        self.count += len(rows)

    def scalar(self, sql):
        return self.count

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back = True


class GeneratedSqlTests(CopyCase):
    def copy_with_fake(self, engine, table):
        tables = finalize_schema(run_db_scan(self.uri(self.src))["data"])
        ddl = generate_ddl(tables, "sqlite", engine, {"name_style": "keep"})
        fake = FakeTarget(engine)
        tinfo = next(t for t in ddl["tables"] if t["name"] == table)
        entry = {"name": table, "target_name": tinfo["target_name"], "rows_source": None, "rows_copied": 0, "rows_target": None, "ok": False}
        src = SourceReader(self.uri(self.src), "sqlite")
        try:
            copy_engine._copy_table(src, fake, "sqlite", engine, tables[table], tinfo, "CREATE TABLE t ()", entry, False, threading.Event(), lambda p: None, 0, 1,
                                    {"rows_copied": 0, "warnings": []})
        finally:
            src.close()
        return fake

    def test_sql_server_inserts_identity_values_explicitly_and_uses_qmark(self):
        fake = self.copy_with_fake("mssql", "productos")
        s = fake.statements
        self.assertEqual(s[0], "CREATE TABLE t ()")
        self.assertEqual(s[1], "SET IDENTITY_INSERT [productos] ON")
        self.assertTrue(s[2].startswith("INSERT INTO [productos] ([id], [sku]") and s[2].count("?") == 9)
        self.assertEqual(s[-1] if "OFF" in s[-1] else s[-2], "SET IDENTITY_INSERT [productos] OFF")
        self.assertEqual(fake.committed, 1)
        self.assertEqual(len(fake.inserted), N_PRODUCTOS)
        self.assertEqual(fake.inserted[0][4], 0)                       # BIT como entero

    def test_postgres_uses_format_placeholders_booleans_and_resets_the_sequence(self):
        fake = self.copy_with_fake("postgres", "productos")
        ins = next(x for x in fake.statements if x.startswith("INSERT"))
        self.assertTrue(ins.count("%s") == 9 and "?" not in ins)
        self.assertTrue(any(x.startswith("SELECT setval(pg_get_serial_sequence('\"productos\"', 'id')") for x in fake.statements))
        self.assertIsInstance(fake.inserted[0][4], bool)
        self.assertIsInstance(fake.inserted[0][6], bytes)

    def test_mysql_keeps_identity_without_extra_statements(self):
        fake = self.copy_with_fake("mysql", "productos")
        self.assertFalse(any("IDENTITY_INSERT" in x or "setval" in x for x in fake.statements))
        self.assertTrue(any(x.startswith("INSERT INTO `productos`") for x in fake.statements))


class ConverterTests(unittest.TestCase):
    def test_booleans_per_engine(self):
        self.assertIs(make_converter("bool", "postgres", "c")(1), True)
        self.assertEqual(make_converter("bool", "mssql", "c")(True), 1)
        self.assertIsNone(make_converter("bool", "mysql", "c")(None))

    def test_json_arrays_and_dicts_become_text(self):
        self.assertEqual(make_converter("json", "mssql", "c")({"a": 1, "ñ": "é"}), '{"a": 1, "ñ": "é"}')
        self.assertEqual(make_converter("other", "mysql", "c")([1, 2]), "[1, 2]")
        self.assertEqual(make_converter("json", "postgres", "c")('{"x":1}'), '{"x":1}')

    def test_dates_and_time_zones(self):
        aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(make_converter("datetime", "mysql", "c")(aware), datetime(2026, 1, 2, 8, 4, 5))          # a UTC sin zona
        self.assertEqual(make_converter("datetime", "sqlite", "c")(aware), "2026-01-02 08:04:05")
        self.assertEqual(make_converter("datetimetz", "mssql", "c")(aware), "2026-01-02 03:04:05-05:00")
        self.assertEqual(make_converter("datetimetz", "postgres", "c")(aware), aware)
        self.assertEqual(make_converter("datetimetz", "postgres", "c")(datetime(2026, 1, 2)).tzinfo, timezone.utc)
        self.assertEqual(make_converter("date", "sqlite", "c")(date(2026, 1, 2)), "2026-01-02")
        self.assertEqual(make_converter("time", "mssql", "c")(timedelta(hours=1, minutes=2, seconds=3)), "01:02:03")

    def test_numbers_binary_and_uuid(self):
        self.assertEqual(make_converter("decimal", "sqlite", "c")(Decimal("12.50")), "12.50")
        self.assertEqual(make_converter("decimal", "mssql", "c")(Decimal("12.50")), Decimal("12.50"))
        self.assertEqual(make_converter("binary", "mssql", "c")(memoryview(b"ab")), b"ab")
        self.assertEqual(make_converter("uuid", "mysql", "c")(__import__("uuid").UUID(int=1)), "00000000-0000-0000-0000-000000000001")

    def test_nul_characters_are_rejected_only_for_postgres_and_never_echo_the_value(self):
        with self.assertRaises(CopyError) as cm:
            make_converter("varchar", "postgres", "nombre")("secreto\x00x")
        self.assertIn("nombre", str(cm.exception))
        self.assertNotIn("secreto", str(cm.exception))
        self.assertEqual(make_converter("varchar", "mysql", "c")("a\x00b"), "a\x00b")


if __name__ == "__main__":
    unittest.main()
