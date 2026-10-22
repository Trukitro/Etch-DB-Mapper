import csv
import io
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

from core import docs_export, joins
from core.api import Api
from core.inference import infer_relations
from core.scanner import build_schema, finalize_schema
from core.storage import Store


def col(name, type_="int", pk=False, null=False, comment=""):
    return {"name": name, "type": type_, "null": null, "pk": pk, "comment": comment}


def schema(**tables):
    return finalize_schema({n: {"columns": cols, "relations": rels, "comment": ""} for n, (cols, rels) in tables.items()})


def shop():
    return schema(
        Customers=([col("CustomerID", pk=True), col("Name", "varchar(50)")], []),
        Orders=([col("OrderID", pk=True), col("CustomerID")], [{"col": "CustomerID", "ref_table": "Customers", "ref_col": "CustomerID"}]),
        Items=([col("ItemID", pk=True), col("OrderID"), col("ProductID")], [{"col": "OrderID", "ref_table": "Orders", "ref_col": "OrderID"}]),
        Products=([col("ProductID", pk=True)], []),
        Island=([col("IslandID", pk=True)], []),
    )


class NativeCommentsTests(unittest.TestCase):
    def test_build_schema_attaches_table_and_column_comments(self):
        raw = {"tables": [("dbo", "Orders")], "columns": [("dbo", "Orders", "OrderID", "int", False), ("dbo", "Orders", "Total", "decimal", True)],
               "pks": [("dbo", "Orders", "OrderID")], "fks": [],
               "comments": [("dbo", "Orders", None, "Pedidos de clientes"), ("dbo", "Orders", "Total", "Importe con IVA"), ("dbo", "Ghost", None, "x")]}
        t = build_schema(raw)["Orders"]
        self.assertEqual(t["comment"], "Pedidos de clientes")
        self.assertEqual({c["name"]: c["comment"] for c in t["columns"]}, {"OrderID": "", "Total": "Importe con IVA"})

    def test_schema_without_comments_key_still_builds(self):
        raw = {"tables": [("main", "t")], "columns": [("main", "t", "id", "int", False)], "pks": [], "fks": []}
        self.assertEqual(build_schema(raw)["t"]["comment"], "")


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name))
        self.store.put("A", {"uri": "sqlite://x.db"})
        self.cid = self.store.get("A")["id"]

    def tearDown(self):
        self._tmp.cleanup()

    def test_table_and_column_notes_roundtrip_and_clear(self):
        self.store.set_annotation(self.cid, "Orders", None, {"note": " Pedidos ", "owner": "Ventas", "tags": ["core", "CORE", " crítico ", ""]})
        self.store.set_annotation(self.cid, "Orders", "Total", {"note": "Con IVA"})
        t = self.store.get_annotations(self.cid)["tables"]["Orders"]
        self.assertEqual((t["note"], t["owner"], t["tags"], t["columns"]), ("Pedidos", "Ventas", ["core", "crítico"], {"Total": "Con IVA"}))
        self.store.set_annotation(self.cid, "Orders", "Total", {"note": ""})
        self.store.set_annotation(self.cid, "Orders", None, {"note": "", "owner": "", "tags": []})
        self.assertEqual(self.store.get_annotations(self.cid)["tables"], {})

    def test_limits_are_enforced(self):
        self.store.set_annotation(self.cid, "T", None, {"note": "x" * 9000, "tags": [f"t{i}" for i in range(50)], "owner": "o" * 500})
        t = self.store.get_annotations(self.cid)["tables"]["T"]
        self.assertEqual((len(t["note"]), len(t["tags"]), len(t["owner"])), (4000, 20, 80))

    def test_survives_new_store_instance(self):
        self.store.set_annotation(self.cid, "T", None, {"note": "hola"})
        self.assertEqual(Store(Path(self._tmp.name)).get_annotations(self.cid)["tables"]["T"]["note"], "hola")


class JoinTests(unittest.TestCase):
    def test_shortest_path_and_sql(self):
        t = shop()
        paths = joins.find_paths(t, infer_relations(t), "Items", "Customers")
        self.assertEqual([s["right"] for s in paths[0]], ["Orders", "Customers"])
        sql = joins.join_sql("postgres", t, paths[0])
        self.assertIn('FROM "Items" AS t1', sql)                       # PostgreSQL: los nombres con mayúsculas llevan comillas
        self.assertIn('INNER JOIN "Orders" AS t2 ON t1."OrderID" = t2."OrderID"', sql)
        self.assertIn('INNER JOIN "Customers" AS t3 ON t2."CustomerID" = t3."CustomerID"', sql)
        low = joins.join_sql("mssql", t, paths[0])
        self.assertIn("FROM Items AS t1", low)
        self.assertTrue(sql.rstrip().endswith(";"))

    def test_inferred_relations_are_used_only_if_requested_and_flagged(self):
        t = shop()
        inferred = infer_relations(t)          # Items.ProductID -> Products (alta confianza)
        self.assertEqual(joins.find_paths(t, inferred, "Items", "Products", include_inferred=False), [])
        p = joins.find_paths(t, inferred, "Items", "Products", include_inferred=True)[0]
        self.assertTrue(p[0]["inferred"])
        self.assertIn("PROBABLES", joins.join_sql("postgres", t, p))

    def test_unreachable_and_invalid_inputs(self):
        t = shop()
        self.assertEqual(joins.find_paths(t, [], "Items", "Island"), [])
        self.assertEqual(joins.find_paths(t, [], "Items", "Items"), [])
        self.assertEqual(joins.find_paths(t, [], "Items", "Nope"), [])

    def test_identifier_quoting_per_engine(self):
        self.assertEqual(joins.quote_ident("mssql", "Order Detail"), "[Order Detail]")
        self.assertEqual(joins.quote_ident("mysql", "order detail"), "`order detail`")
        self.assertEqual(joins.quote_ident("postgres", "Order Detail"), '"Order Detail"')
        self.assertEqual(joins.quote_ident("mssql", "a]b c"), "[a]]b c]")
        self.assertEqual(joins.quote_ident("postgres", "plain_name"), "plain_name")
        self.assertEqual(joins.quote_ident("postgres", "Prueba"), '"Prueba"')        # PostgreSQL pliega a minúsculas
        self.assertEqual(joins.quote_ident("mssql", "Prueba"), "Prueba")
        self.assertEqual(joins.quote_ident("postgres", "order"), '"order"')          # palabra reservada
        self.assertEqual(joins.quote_ident("mssql", "user"), "[user]")

    def test_schema_is_qualified(self):
        t = finalize_schema({"A": {"schema": "dbo", "name": "A", "columns": [col("id", pk=True)], "relations": []},
                             "B": {"schema": "dbo", "name": "B", "columns": [col("id", pk=True), col("a_id")],
                                   "relations": [{"col": "a_id", "ref_table": "A", "ref_col": "id"}]}})
        sql = joins.join_sql("mssql", t, joins.find_paths(t, [], "B", "A")[0])
        self.assertIn("FROM dbo.B AS t1", sql)

    def test_diamond_returns_multiple_paths_shortest_first(self):
        t = schema(A=([col("id", pk=True), col("b_id"), col("c_id")], [{"col": "b_id", "ref_table": "B", "ref_col": "id"}, {"col": "c_id", "ref_table": "C", "ref_col": "id"}]),
                   B=([col("id", pk=True), col("d_id")], [{"col": "d_id", "ref_table": "D", "ref_col": "id"}]),
                   C=([col("id", pk=True), col("d_id")], [{"col": "d_id", "ref_table": "D", "ref_col": "id"}]),
                   D=([col("id", pk=True)], []))
        paths = joins.find_paths(t, [], "A", "D")
        self.assertEqual(len(paths), 2)
        self.assertEqual({tuple(s["right"] for s in p) for p in paths}, {("B", "D"), ("C", "D")})


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.t = shop()
        self.t["Orders"]["comment"] = "Pedidos | de <clientes>"
        ann = {"tables": {"Customers": {"note": "Personas que compran", "owner": "Ventas", "tags": ["core"], "columns": {"Name": "Nombre completo"}},
                          "Island": {"note": "</script><script>alert(1)</script>"}}}
        self.inferred = infer_relations(self.t)
        self.cards = docs_export.collect(self.t, self.inferred, ann)

    def test_description_prefers_user_note_over_native_comment(self):
        by = {c["name"]: c for c in self.cards}
        self.assertEqual(by["Customers"]["description"], "Personas que compran")
        self.assertEqual(by["Orders"]["description"], "Pedidos | de <clientes>")
        self.assertEqual({c["name"]: c["description"] for c in by["Customers"]["columns"]}["Name"], "Nombre completo")

    def test_markdown_has_tables_columns_and_escapes_pipes(self):
        md = docs_export.export_markdown("Tienda", "postgres", self.cards, "2026-10-21")
        self.assertIn("## `Customers`", md)
        self.assertIn("**Responsable:** Ventas", md)
        self.assertIn("Pedidos \\| de <clientes>", md)
        self.assertIn("Relaciones probables", md)

    def test_csv_is_valid_and_has_bom(self):
        text = docs_export.export_csv(self.cards)
        self.assertTrue(text.startswith("﻿"))
        rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
        self.assertEqual(rows[0][1], "tabla")
        self.assertEqual(len(rows) - 1, sum(len(c["columns"]) for c in self.cards))

    def test_html_report_escapes_user_text_and_is_self_contained(self):
        out = docs_export.export_html("Tie<nda>", "postgres", self.cards, self.inferred, "2026-10-21", {"Orders": {"x": 1, "y": 2}})
        self.assertNotIn("<script>alert(1)</script>", out)          # la nota maliciosa no se ejecuta
        self.assertNotIn("Tie<nda>", out)
        self.assertIn("&lt;/script&gt;", out)
        self.assertIn("cytoscape", out)                              # mapa incrustado
        self.assertNotRegex(out, r'(src|href)="https?://(?!github\.com)')   # sin recursos remotos
        m = re.search(r'<script type="application/json" id="etch-data">(.*?)</script>', out, re.S)
        data = json.loads(m.group(1).replace("<\\/", "</"))
        self.assertIn("Orders", data["index"])
        self.assertTrue(any(e["inf"] for e in data["edges"]))
        self.assertEqual(out.count("</script>"), out.count("<script"))        # ningún </script> suelto roto

    def test_html_without_map_is_lighter(self):
        with_map = docs_export.export_html("x", "pg", self.cards, self.inferred, "")
        without = docs_export.export_html("x", "pg", self.cards, self.inferred, "", with_map=False)
        self.assertLess(len(without), len(with_map) / 5)

    def test_filename_is_safe(self):
        self.assertEqual(docs_export.safe_filename("Base: ventas/2026?", "md"), "Base_ ventas_2026.md")


class FakeWindow:
    def __init__(self):
        self.done = threading.Event()

    def evaluate_js(self, code):
        if "scan_finished" in code:
            self.done.set()


class DocsApiTests(unittest.TestCase):
    def test_end_to_end_with_demo_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            win = FakeWindow()
            api = Api(Store(Path(tmp)), win)
            api.create_demo_connection()
            alias = api.list_connections()[0]["alias"]
            self.assertFalse(api.export_docs(alias, "markdown")["ok"])           # aún sin escanear
            api.start_scan(alias)
            self.assertTrue(win.done.wait(30))
            self.assertTrue(api.save_annotation(alias, "customers", None, {"note": "Clientes", "tags": ["core"]})["ok"])
            self.assertTrue(api.save_annotation(alias, "customers", "email", {"note": "Único"})["ok"])
            s = api.get_schema(alias)
            self.assertEqual(s["annotations"]["tables"]["customers"]["note"], "Clientes")
            r = api.find_paths(alias, "order_items", "customers")
            self.assertTrue(r["ok"] and r["paths"])
            self.assertIn("INNER JOIN", r["paths"][0]["sql"])
            self.assertFalse(api.find_paths(alias, "customers", "customers")["ok"])
            self.assertFalse(api.find_paths(alias, "customers", "inexistente")["ok"])
            for kind, ext in (("markdown", "md"), ("csv", "csv"), ("html", "html")):
                e = api.export_docs(alias, kind)
                self.assertTrue(e["ok"], kind)
                self.assertTrue(e["filename"].endswith("." + ext))
                self.assertIn("customers", e["content"])
                self.assertIn("Clientes", e["content"])
            self.assertFalse(api.export_docs(alias, "pdf")["ok"])


if __name__ == "__main__":
    unittest.main()
