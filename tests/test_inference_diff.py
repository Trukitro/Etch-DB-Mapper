import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import updates
from core.api import Api
from core.diff import describe, diff_schemas
from core.inference import infer_relations
from core.scanner import finalize_schema
from core.storage import Store, compact_schema


def col(name, type_="int", pk=False, null=False):
    return {"name": name, "type": type_, "null": null, "pk": pk}


def schema(**tables):
    return finalize_schema({n: {"columns": cols, "relations": rels} for n, (cols, rels) in tables.items()})


class InferenceTests(unittest.TestCase):
    def test_same_name_as_unique_pk_is_high_confidence(self):
        t = schema(Customers=([col("CustomerID", pk=True), col("Name", "varchar(50)")], []),
                   Orders=([col("OrderID", pk=True), col("CustomerID")], []))
        r = infer_relations(t)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["table"], r[0]["col"], r[0]["ref_table"], r[0]["ref_col"], r[0]["confidence"]),
                         ("Orders", "CustomerID", "Customers", "CustomerID", "high"))

    def test_stem_matches_table_name_with_generic_pk(self):
        t = schema(Cliente=([col("id", pk=True)], []), Pedido=([col("id", pk=True), col("ClienteID")], []))
        r = infer_relations(t)
        self.assertEqual([(x["table"], x["ref_table"], x["confidence"]) for x in r], [("Pedido", "Cliente", "medium")])

    def test_plural_and_prefixed_table_names(self):
        t = schema(tbl_Users=([col("id", pk=True)], []), Posts=([col("id", pk=True), col("user_id")], []))
        self.assertEqual([(x["table"], x["ref_table"]) for x in infer_relations(t)], [("Posts", "tbl_Users")])

    def test_declared_fks_are_not_repeated(self):
        t = schema(A=([col("AID", pk=True)], []), B=([col("BID", pk=True), col("AID")], [{"col": "AID", "ref_table": "A", "ref_col": "AID"}]))
        self.assertEqual(infer_relations(t), [])

    def test_incompatible_types_are_skipped(self):
        t = schema(Customers=([col("CustomerID", "int", pk=True)], []), Orders=([col("OrderID", pk=True), col("CustomerID", "varchar(10)")], []))
        self.assertEqual(infer_relations(t), [])

    def test_ambiguous_targets_are_skipped(self):
        t = schema(A_User=([col("id", pk=True)], []), B_User=([col("id", pk=True)], []), Log=([col("id", pk=True), col("UserID")], []))
        self.assertEqual(infer_relations(t), [])

    def test_ambiguity_resolved_by_same_prefix(self):
        t = schema(ETS_User=([col("id", pk=True)], []), Cat_User=([col("id", pk=True)], []), ETS_Email=([col("id", pk=True), col("UserID")], []))
        r = infer_relations(t)
        self.assertEqual([(x["table"], x["ref_table"]) for x in r], [("ETS_Email", "ETS_User")])

    def test_own_primary_key_and_generic_id_are_not_relations(self):
        t = schema(Customers=([col("CustomerID", pk=True)], []), Other=([col("id", pk=True), col("id2")], []))
        self.assertEqual(infer_relations(t), [])

    def test_valid_like_words_do_not_trigger(self):
        t = schema(Val=([col("id", pk=True)], []), T=([col("id", pk=True), col("Valid"), col("Android")], []))
        self.assertEqual(infer_relations(t), [])


class DiffTests(unittest.TestCase):
    def test_all_kinds_of_change(self):
        old = schema(A=([col("id", pk=True), col("x", "int"), col("gone")], []), Gone=([col("id")], []), Same=([col("id")], []))
        new = schema(A=([col("id", pk=True), col("x", "bigint"), col("extra", "text")], [{"col": "x", "ref_table": "New", "ref_col": "id"}]),
                     New=([col("id", pk=True)], []), Same=([col("id")], []))
        d = diff_schemas(compact_schema(old), compact_schema(new))
        self.assertEqual([t["name"] for t in d["added_tables"]], ["New"])
        self.assertEqual([t["name"] for t in d["removed_tables"]], ["Gone"])
        a = d["changed_tables"]["A"]
        self.assertEqual([c["name"] for c in a["added_columns"]], ["extra"])
        self.assertEqual([c["name"] for c in a["removed_columns"]], ["gone"])
        self.assertEqual(a["modified_columns"][0]["changes"]["type"], ["int", "bigint"])
        self.assertEqual(len(a["added_relations"]), 1)
        self.assertNotIn("Same", d["changed_tables"])
        self.assertIn("tabla nueva", describe(d["summary"]))

    def test_identical_schemas_have_no_changes(self):
        s = compact_schema(schema(A=([col("id")], [])))
        d = diff_schemas(s, s)
        self.assertEqual(d["summary"]["total"], 0)
        self.assertEqual(describe(d["summary"]), "sin cambios")


class FakeWindow:
    def __init__(self):
        self.events = []

    def evaluate_js(self, code):
        self.events.append(code)


class HistoryApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.api = Api(Store(Path(self._tmp.name)), FakeWindow())

    def tearDown(self):
        self._tmp.cleanup()

    def _scan(self, alias):
        import threading
        done = threading.Event()
        orig = self.api._emit

        def emit(event, payload):
            orig(event, payload)
            if event == "scan_finished":
                self.last = payload
                done.set()
        self.api._emit = emit
        self.assertTrue(self.api.start_scan(alias)["ok"])
        self.assertTrue(done.wait(30))

    def test_history_and_compare_after_schema_change(self):
        import sqlite3
        self.api.create_demo_connection()
        alias = self.api.list_connections()[0]["alias"]
        self._scan(alias)
        self.assertIsNone(self.last["changes"])                     # primer escaneo: nada con qué comparar
        self._scan(alias)
        self.assertEqual(self.last["changes"]["total"], 0)           # igual: sin cambios
        self.assertEqual(self.api.get_schema(alias)["versions"], 1)
        db = Path(self._tmp.name) / "demo" / "tienda.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE nueva_tabla (id INTEGER PRIMARY KEY, note TEXT)")
        con.execute("ALTER TABLE customers ADD COLUMN loyalty_points INTEGER")
        con.commit()
        con.close()
        self._scan(alias)
        self.assertEqual(self.last["changes"]["added_tables"], 1)
        self.assertEqual(self.last["changes"]["added_columns"], 1)
        self.assertEqual(self.api.get_schema(alias)["versions"], 2)
        cmp = self.api.compare_versions(alias)
        self.assertTrue(cmp["ok"])
        self.assertEqual([t["name"] for t in cmp["diff"]["added_tables"]], ["nueva_tabla"])
        self.assertIn("loyalty_points", [c["name"] for c in cmp["diff"]["changed_tables"]["customers"]["added_columns"]])

    def test_compare_needs_two_versions(self):
        self.api.create_demo_connection()
        alias = self.api.list_connections()[0]["alias"]
        self.assertFalse(self.api.compare_versions(alias)["ok"])

    def test_get_schema_includes_inferred(self):
        self.api.create_demo_connection()
        alias = self.api.list_connections()[0]["alias"]
        self._scan(alias)
        s = self.api.get_schema(alias)
        self.assertIn("inferred", s)
        self.assertEqual(s["meta"]["inferred_count"], len(s["inferred"]))


class UpdatesTests(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(updates.parse_version("v2.1.1"), (2, 1, 1))
        self.assertIsNone(updates.parse_version("latest"))

    def test_newer_version_detected_and_url_is_trusted(self):
        fake = lambda url, timeout: {"tag_name": "v9.0.0", "html_url": "https://evil.example/x"}  # noqa: E731
        r = updates.check_latest("2.1.1", fetch=fake)
        self.assertTrue(r["ok"] and r["newer"])
        self.assertTrue(r["url"].startswith("https://github.com/Trukitro/Etch-DB-Mapper/"))

    def test_same_version_not_newer(self):
        r = updates.check_latest("2.1.1", fetch=lambda u, t: {"tag_name": "v2.1.1", "html_url": "https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v2.1.1"})
        self.assertFalse(r["newer"])

    def test_network_failure_is_not_an_exception(self):
        def boom(url, timeout):
            raise OSError("sin red")
        r = updates.check_latest("2.1.1", fetch=boom)
        self.assertFalse(r["ok"])

    def test_api_respects_setting_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = Api(Store(Path(tmp)))
            api._store.patch_settings({"check_updates": False})
            with mock.patch.object(updates, "check_latest") as m:
                self.assertTrue(api.check_updates()["skipped"])
                m.assert_not_called()
                m.return_value = {"ok": True, "newer": False}
                self.assertTrue(api.check_updates(force=True)["ok"])      # "buscar ahora" ignora el ajuste
            with mock.patch.dict("os.environ", {"ETCH_NO_UPDATE_CHECK": "1"}):
                self.assertTrue(api.check_updates(force=True)["skipped"])


if __name__ == "__main__":
    unittest.main()
