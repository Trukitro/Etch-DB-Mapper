import re
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from core.api import Api
from core.demo import create_demo_db
from core.migrate import TARGETS, generate_ddl, parse_type, render_type, translate_default
from core.scanner import finalize_schema, run_db_scan
from core.storage import Store


def col(name, type_="integer", pk=False, null=False, identity=False, default=None, prec=None, comment=""):
    return {"name": name, "type": type_, "null": null, "pk": pk, "identity": identity, "default": default, "prec": prec, "comment": comment}


def schema(**tables):
    out = {}
    for n, spec in tables.items():
        cols, rels = spec[0], spec[1]
        extra = spec[2] if len(spec) > 2 else {}
        out[n] = {"schema": extra.get("schema", ""), "name": extra.get("name", n), "comment": extra.get("comment", ""),
                  "columns": cols, "relations": rels, "uniques": extra.get("uniques", [])}
    return finalize_schema(out)


def pg_like():
    """Imita el esquema real de un PostgreSQL con los casos difíciles."""
    return schema(
        Prueba=([col("id", pk=True, identity=True, default="nextval('\"Prueba_id_seq\"'::regclass)"), col("codigo", "varchar(20)"),
                 col("salario", "numeric", null=True, prec=[10, 2]), col("fecha", "date", null=True, default="CURRENT_DATE"),
                 col("creado", "timestamptz", null=True, default="CURRENT_TIMESTAMP"), col("activo", "boolean", null=True, default="true"),
                 col("prefs", "jsonb", null=True), col("tags", "ARRAY", null=True), col("ref", "uuid", null=True, default="gen_random_uuid()"),
                 col("notas", "text", null=True)], [], {"uniques": [["codigo"]]}),
        Usuario=([col("id", pk=True, identity=True), col("jefe_id", null=True)], [{"col": "jefe_id", "ref_table": "Usuario", "ref_col": "id"}]),
        Favoritos=([col("usuario_id", pk=True), col("producto_id", pk=True)],
                   [{"col": "usuario_id", "ref_table": "Usuario", "ref_col": "id"}, {"col": "producto_id", "ref_table": "Producto", "ref_col": "id"}]),
        Producto=([col("id", pk=True, identity=True)], []),
    )


def executable(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))


class TypeMappingTests(unittest.TestCase):
    def r(self, type_, target, source="postgres", prec=None):
        return render_type(parse_type(type_, prec, source), target, source)[0]

    def test_integers_and_numbers(self):
        self.assertEqual([self.r("integer", t) for t in TARGETS], ["INTEGER", "INT", "INT", "INTEGER"])
        self.assertEqual(self.r("bigint", "mssql"), "BIGINT")
        self.assertEqual(self.r("tinyint", "postgres", "mssql"), "SMALLINT")
        self.assertEqual(self.r("numeric", "mssql", prec=[10, 2]), "DECIMAL(10,2)")
        self.assertEqual(self.r("numeric", "postgres", prec=[10, 2]), "NUMERIC(10,2)")
        self.assertEqual(self.r("decimal(18,4)", "mysql", "mssql"), "DECIMAL(18,4)")
        self.assertEqual(self.r("money", "postgres", "mssql"), "NUMERIC(19,4)")
        self.assertEqual(self.r("double", "mssql"), "FLOAT")
        self.assertEqual(self.r("boolean", "mssql"), "BIT")
        self.assertEqual(self.r("bit", "postgres", "mssql"), "BOOLEAN")

    def test_strings_follow_target_limits(self):
        self.assertEqual(self.r("varchar(50)", "mssql"), "NVARCHAR(50)")                  # PostgreSQL guarda Unicode
        self.assertEqual(self.r("varchar(50)", "mssql", "mssql"), "VARCHAR(50)")          # SQL Server -> SQL Server conserva
        self.assertEqual(self.r("nvarchar(50)", "mssql", "mssql"), "NVARCHAR(50)")
        self.assertEqual(self.r("varchar(max)", "postgres", "mssql"), "TEXT")
        self.assertEqual(self.r("varchar(max)", "mysql", "mssql"), "LONGTEXT")
        self.assertEqual(self.r("varchar(9000)", "mssql", "mssql"), "VARCHAR(MAX)")
        self.assertEqual(self.r("varchar(20000)", "mysql"), "LONGTEXT")
        self.assertEqual(self.r("text", "mssql"), "NVARCHAR(MAX)")
        self.assertEqual(self.r("char(3)", "postgres"), "CHAR(3)")

    def test_dates_and_special_types(self):
        self.assertEqual(self.r("datetime2", "postgres", "mssql"), "TIMESTAMP")
        self.assertEqual(self.r("datetimeoffset", "postgres", "mssql"), "TIMESTAMPTZ")
        self.assertEqual(self.r("timestamptz", "mssql"), "DATETIMEOFFSET")
        self.assertEqual(self.r("uniqueidentifier", "mysql", "mssql"), "CHAR(36)")
        self.assertEqual(self.r("uuid", "mssql"), "UNIQUEIDENTIFIER")
        self.assertEqual(self.r("bytea", "mssql"), "VARBINARY(MAX)")
        self.assertEqual(self.r("jsonb", "postgres"), "JSONB")
        self.assertEqual(self.r("json", "mssql", "mysql"), "NVARCHAR(MAX)")
        # timestamp de SQL Server es rowversion, no una fecha
        sql, notes = render_type(parse_type("timestamp", None, "mssql"), "postgres", "mssql")
        self.assertEqual(sql, "BYTEA")
        self.assertTrue(notes)
        self.assertEqual(self.r("timestamp", "mssql", "postgres"), "DATETIME2")

    def test_unknown_types_fall_back_with_a_warning(self):
        sql, notes = render_type(parse_type("geometry", None, "postgres"), "mysql", "postgres")
        self.assertEqual(sql, "LONGTEXT")
        self.assertTrue(notes)


class DefaultTests(unittest.TestCase):
    def test_translations(self):
        t = translate_default
        self.assertEqual(t("((0))", "int", "postgres", "mssql")[0], "0")
        self.assertEqual(t("(getdate())", "datetime", "postgres", "mssql")[0], "CURRENT_TIMESTAMP")
        self.assertEqual(t("now()", "datetime", "mssql", "postgres")[0], "SYSDATETIME()")
        self.assertEqual(t("('abc')", "varchar", "mysql", "mssql")[0], "'abc'")
        self.assertEqual(t("'abc'::character varying", "varchar", "mssql", "postgres")[0], "'abc'")
        self.assertEqual(t("true", "bool", "mssql", "postgres")[0], "1")
        self.assertEqual(t("((1))", "bool", "postgres", "mssql")[0], "true")
        self.assertEqual(t("newid()", "uuid", "postgres", "mssql")[0], "gen_random_uuid()")
        self.assertEqual(t("CURRENT_DATE", "date", "mssql", "postgres")[0], "CAST(GETDATE() AS DATE)")
        self.assertEqual(t("abc", "varchar", "postgres", "mysql")[0], "'abc'")    # MySQL devuelve literales sin comillas

    def test_unknown_defaults_are_skipped_with_warning_never_guessed(self):
        sql, warn = translate_default("dbo.MiFuncion(1)", "int", "postgres", "mssql")
        self.assertIsNone(sql)
        self.assertIn("no se tradujo", warn)
        self.assertEqual(translate_default(None, "int", "postgres", "mssql"), (None, None))
        self.assertEqual(translate_default("NULL", "int", "postgres", "mssql"), (None, None))
        self.assertIsNone(translate_default("getdate()", "varchar", "postgres", "mssql")[0])


class GenerateTests(unittest.TestCase):
    def test_every_target_generates_without_errors(self):
        for target in TARGETS:
            out = generate_ddl(pg_like(), "postgres", target, alias="x")
            self.assertEqual(out["stats"]["errors"], 0, (target, out["warnings"]))
            self.assertEqual(out["stats"]["tables"], 4)
            self.assertIn("CREATE TABLE", out["sql"])

    def test_script_is_creation_only(self):
        for target in TARGETS:
            body = executable(generate_ddl(pg_like(), "postgres", target)["sql"])
            self.assertNotRegex(body, r"(?i)\b(DROP|TRUNCATE|DELETE|UPDATE|INSERT|IF\s+NOT\s+EXISTS)\b", target)

    def test_identity_per_engine(self):
        pg = generate_ddl(pg_like(), "postgres", "postgres")["sql"]
        self.assertIn("GENERATED BY DEFAULT AS IDENTITY", pg)
        self.assertNotIn("nextval", pg)
        self.assertIn("IDENTITY(1,1)", generate_ddl(pg_like(), "postgres", "mssql")["sql"])
        self.assertIn("AUTO_INCREMENT", generate_ddl(pg_like(), "postgres", "mysql")["sql"])
        self.assertIn('"id" INTEGER PRIMARY KEY', generate_ddl(pg_like(), "postgres", "sqlite")["sql"])
        off = generate_ddl(pg_like(), "postgres", "mssql", {"include_identity": False})
        self.assertNotIn("IDENTITY", off["sql"])

    def test_foreign_keys_come_after_all_tables_and_parents_first(self):
        sql = generate_ddl(pg_like(), "postgres", "mssql")["sql"]
        self.assertGreater(sql.index("ALTER TABLE [Favoritos] ADD CONSTRAINT"), sql.rindex("CREATE TABLE"))
        self.assertLess(sql.index("CREATE TABLE [Usuario]"), sql.index("CREATE TABLE [Favoritos]"))
        self.assertLess(sql.index("CREATE TABLE [Producto]"), sql.index("CREATE TABLE [Favoritos]"))
        self.assertIn("REFERENCES [Usuario] ([id])", sql)               # autorreferencia sin problema

    def test_composite_foreign_key_is_grouped(self):
        t = schema(Padre=([col("a", pk=True), col("b", pk=True)], []),
                   Hijo=([col("id", pk=True), col("pa"), col("pb")],
                         [{"col": "pa", "ref_table": "Padre", "ref_col": "a"}, {"col": "pb", "ref_table": "Padre", "ref_col": "b"}]))
        out = generate_ddl(t, "mssql", "postgres")
        self.assertEqual(out["stats"]["foreign_keys"], 1)
        self.assertIn("FOREIGN KEY (pa, pb) REFERENCES padre (a, b)", out["sql"])

    def test_name_style_prefix_and_schema(self):
        lower = generate_ddl(pg_like(), "mssql", "postgres")["sql"]
        self.assertIn("CREATE TABLE prueba (", lower)                 # postgres: minúsculas sin comillas por defecto
        keep = generate_ddl(pg_like(), "postgres", "postgres", {"name_style": "keep"})["sql"]
        self.assertIn('CREATE TABLE "Prueba" (', keep)
        pre = generate_ddl(pg_like(), "postgres", "mssql", {"table_prefix": "mig_"})["sql"]
        self.assertIn("CREATE TABLE [mig_Prueba]", pre)
        sch = generate_ddl(pg_like(), "postgres", "mssql", {"target_schema": "migrado"})["sql"]
        self.assertIn("CREATE SCHEMA [migrado];\nGO", sch)
        self.assertIn("CREATE TABLE [migrado].[Prueba]", sch)
        self.assertIn("REFERENCES [migrado].[Usuario]", sch)
        my = generate_ddl(pg_like(), "postgres", "mysql", {"target_schema": "migrado"})
        self.assertNotIn("CREATE SCHEMA", my["sql"])
        self.assertTrue(any("esquemas" in w["message"] for w in my["warnings"]))

    def test_source_schemas_are_kept_or_flattened(self):
        t = schema(Ventas=([col("id", pk=True)], [], {"schema": "sales"}))
        self.assertIn("CREATE SCHEMA [sales]", generate_ddl(t, "mssql", "mssql")["sql"])
        self.assertIn("CREATE TABLE sales_Ventas", generate_ddl(t, "mssql", "sqlite", {"name_style": "keep"})["sql"].replace('"', ""))

    def test_invalid_options_and_empty_input(self):
        with self.assertRaises(ValueError):
            generate_ddl(pg_like(), "postgres", "oracle")
        with self.assertRaises(ValueError):
            generate_ddl(pg_like(), "postgres", "mssql", {"target_schema": "x; DROP TABLE y"})
        with self.assertRaises(ValueError):
            generate_ddl(pg_like(), "postgres", "mssql", {"table_prefix": "1abc"})
        with self.assertRaises(ValueError):
            generate_ddl(pg_like(), "postgres", "mssql", {"only": ["NoExiste"]})

    def test_name_collisions_and_long_names_are_errors(self):
        t = schema(Aa=([col("id", pk=True)], []), AA=([col("id", pk=True)], []))
        out = generate_ddl(t, "mssql", "postgres")
        self.assertGreaterEqual(out["stats"]["errors"], 1)
        long_name = "x" * 70
        t2 = schema(**{long_name: ([col("id", pk=True)], [])})
        out2 = generate_ddl(t2, "mssql", "postgres")
        self.assertGreaterEqual(out2["stats"]["errors"], 1)
        self.assertTrue(all(len(x["target_name"]) <= 63 for x in out2["tables"]))

    def test_subset_skips_foreign_keys_to_excluded_tables(self):
        out = generate_ddl(pg_like(), "postgres", "mssql", {"only": ["Favoritos", "Usuario"]})
        self.assertEqual(out["stats"]["tables"], 2)
        self.assertEqual(out["stats"]["foreign_keys"], 2)      # la autorreferencia de Usuario + Favoritos -> Usuario
        self.assertNotIn("REFERENCES [Producto]", out["sql"])
        self.assertTrue(any("omitida" in w["message"] for w in out["warnings"]))

    def test_comments_and_quotes_are_escaped(self):
        t = schema(T=([col("id", pk=True), col("c", "text", null=True, comment="it's a 'quote'")], [], {"comment": "Tabla de O'Brien"}))
        self.assertIn("COMMENT ON TABLE t IS 'Tabla de O''Brien';", generate_ddl(t, "postgres", "postgres")["sql"])
        self.assertIn("sp_addextendedproperty @name = N'MS_Description', @value = N'it''s a ''quote'''", generate_ddl(t, "postgres", "mssql")["sql"])
        self.assertIn("COMMENT 'it''s a ''quote'''", generate_ddl(t, "postgres", "mysql")["sql"])
        self.assertNotIn("COMMENT", generate_ddl(t, "postgres", "mysql", {"include_comments": False})["sql"])

    def test_user_notes_override_native_comments(self):
        t = schema(T=([col("id", pk=True)], [], {"comment": "de la base"}))
        out = generate_ddl(t, "postgres", "postgres", descriptions={"T": {"table": "mi nota", "columns": {}}})
        self.assertIn("IS 'mi nota'", out["sql"])

    def test_mapping_preview_lists_every_column(self):
        out = generate_ddl(pg_like(), "postgres", "mssql")
        prueba = next(t for t in out["tables"] if t["name"] == "Prueba")
        self.assertEqual(len(prueba["columns"]), 10)
        sal = next(c for c in prueba["columns"] if c["name"] == "salario")
        self.assertEqual((sal["source_type"], sal["target_type"]), ("numeric", "DECIMAL(10,2)"))


class KeyTypeTests(unittest.TestCase):
    def test_text_keys_are_bounded_for_sql_server_and_mysql(self):
        t = schema(Cfg=([col("key", "text", pk=True), col("slug", "varchar(2000)"), col("value", "text", null=True)], [], {"uniques": [["slug"]]}),
                   Child=([col("id", pk=True), col("cfg_key", "text")], [{"col": "cfg_key", "ref_table": "Cfg", "ref_col": "key"}]))
        ms = generate_ddl(t, "sqlite", "mssql")
        cfg = next(x for x in ms["tables"] if x["name"] == "Cfg")
        types = {c["name"]: c["target_type"] for c in cfg["columns"]}
        self.assertEqual(types["key"], "NVARCHAR(450)")        # PK
        self.assertEqual(types["slug"], "NVARCHAR(450)")       # UNIQUE demasiado largo
        self.assertEqual(types["value"], "NVARCHAR(MAX)")      # columna normal: sin límite
        child = next(x for x in ms["tables"] if x["name"] == "Child")
        self.assertEqual(next(c for c in child["columns"] if c["name"] == "cfg_key")["target_type"], "NVARCHAR(450)")   # FK = mismo tipo que el padre
        self.assertTrue(any("clave" in w["message"] for w in ms["warnings"]))
        my = generate_ddl(t, "sqlite", "mysql")
        mtypes = {c["name"]: c["target_type"] for c in next(x for x in my["tables"] if x["name"] == "Cfg")["columns"]}
        self.assertEqual((mtypes["key"], mtypes["slug"], mtypes["value"]), ("VARCHAR(255)", "VARCHAR(768)", "LONGTEXT"))
        pg = generate_ddl(t, "sqlite", "postgres")
        self.assertTrue(all(c["target_type"] in ("TEXT", "VARCHAR(2000)", "INTEGER") for x in pg["tables"] for c in x["columns"]))


class SqliteExecutionTests(unittest.TestCase):
    """El script de SQLite SÍ se ejecuta de verdad (sqlite3 viene con Python): prueba real de sintaxis y de fidelidad."""

    def test_pg_like_schema_executes_in_sqlite(self):
        sql = generate_ddl(pg_like(), "postgres", "sqlite")["sql"]
        con = sqlite3.connect(":memory:")
        con.executescript(sql)
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(names, {"Prueba", "Usuario", "Favoritos", "Producto"})
        con.close()

    def test_roundtrip_demo_schema_sqlite_to_sqlite_is_equivalent(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = create_demo_db(Path(tmp) / "src.sqlite")
            scanned = run_db_scan(src)
            self.assertEqual(scanned["status"], "success")
            tables = finalize_schema(scanned["data"])
            out = generate_ddl(tables, "sqlite", "sqlite", {"name_style": "keep"}, alias="demo")
            self.assertEqual(out["stats"]["errors"], 0, out["warnings"])
            dst = Path(tmp) / "dst.sqlite"
            con = sqlite3.connect(dst)
            con.executescript(out["sql"])
            con.close()
            copy = finalize_schema(run_db_scan("sqlite://" + str(dst).replace("\\", "/"))["data"])
        self.assertEqual(set(tables), set(copy))
        for name, t in tables.items():
            self.assertEqual([c["name"] for c in t["columns"]], [c["name"] for c in copy[name]["columns"]], name)
            self.assertEqual([c["pk"] for c in t["columns"]], [c["pk"] for c in copy[name]["columns"]], name)
            self.assertEqual({(r["col"], r["ref_table"], r["ref_col"]) for r in t["relations"]},
                             {(r["col"], r["ref_table"], r["ref_col"]) for r in copy[name]["relations"]}, name)
            self.assertEqual(sorted(map(tuple, t["uniques"])), sorted(map(tuple, copy[name]["uniques"])), name)


class ScannerExtrasTests(unittest.TestCase):
    def test_sqlite_scan_reads_identity_defaults_and_uniques(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.sqlite"
            con = sqlite3.connect(path)
            con.executescript("CREATE TABLE a (id INTEGER PRIMARY KEY, code TEXT UNIQUE, qty INTEGER DEFAULT 5, note TEXT, UNIQUE (qty, note));")
            con.close()
            t = finalize_schema(run_db_scan("sqlite://" + str(path).replace("\\", "/"))["data"])["a"]
        cols = {c["name"]: c for c in t["columns"]}
        self.assertTrue(cols["id"]["identity"])
        self.assertFalse(cols["qty"]["identity"])
        self.assertEqual(cols["qty"]["default"], "5")
        self.assertEqual(sorted(map(tuple, t["uniques"])), [("code",), ("qty", "note")])

    def test_old_saved_schemas_without_new_fields_still_work(self):
        legacy = {"t": {"columns": [{"name": "id", "type": "int", "null": "NO", "is_pk": True}], "relations": []}}
        t = finalize_schema(legacy)["t"]
        self.assertFalse(t["columns"][0]["identity"])
        self.assertEqual(t["uniques"], [])
        out = generate_ddl(finalize_schema(legacy), "mssql", "postgres")
        self.assertEqual(out["stats"]["tables"], 1)


class FakeWindow:
    def __init__(self):
        self.done = threading.Event()

    def evaluate_js(self, code):
        if "scan_finished" in code:
            self.done.set()


class MigrationApiTests(unittest.TestCase):
    def test_plan_migration_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            win = FakeWindow()
            api = Api(Store(Path(tmp)), win)
            api.create_demo_connection()
            alias = api.list_connections()[0]["alias"]
            self.assertFalse(api.plan_migration(alias, "mssql")["ok"])                    # sin escanear
            api.start_scan(alias)
            self.assertTrue(win.done.wait(30))
            api.save_annotation(alias, "customers", None, {"note": "Clientes de la tienda"})
            self.assertEqual({t["id"] for t in api.list_migration_targets()["targets"]}, set(TARGETS))
            r = api.plan_migration(alias, "mssql", {"target_schema": "migrado"})
            self.assertTrue(r["ok"], r)
            self.assertGreater(r["stats"]["tables"], 10)
            self.assertIn("CREATE TABLE [migrado].[customers]", r["sql"])
            self.assertIn("Clientes de la tienda", r["sql"])                              # la nota del usuario viaja
            self.assertTrue(r["file_content"].startswith("﻿"))
            self.assertTrue(r["filename"].endswith(".sql"))
            self.assertFalse(api.plan_migration(alias, "oracle")["ok"])
            self.assertFalse(api.plan_migration(alias, "mssql", {"target_schema": "a b"})["ok"])
            self.assertFalse(api.plan_migration("noexiste", "mssql")["ok"])


if __name__ == "__main__":
    unittest.main()
