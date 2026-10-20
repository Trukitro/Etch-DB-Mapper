import tempfile
import unittest
from pathlib import Path

from core.demo import create_demo_db
from core.scanner import (
    compute_meta, detect_engine, finalize_schema, inspect_uri, mask_uri, run_db_scan, summarize_error,
)


class ScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.uri = create_demo_db(Path(cls._tmp.name) / "demo.sqlite")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_detect_engine(self):
        self.assertEqual(detect_engine("postgres://u:p@h/db"), "postgres")
        self.assertEqual(detect_engine("mssql4://u:p@h/db"), "mssql")
        self.assertEqual(detect_engine("mysql://u:p@h/db"), "mysql")
        self.assertEqual(detect_engine("sqlite://x.db"), "sqlite")
        self.assertIsNone(detect_engine("sin-prefijo"))

    def test_mask_uri_hides_password(self):
        masked = mask_uri("postgres://usuario:SuperSecreta@10.0.0.1:5432/db")
        self.assertNotIn("SuperSecreta", masked)
        self.assertIn("usuario", masked)
        self.assertIn("10.0.0.1:5432/db", masked)

    def test_inspect_uri_sqlite_has_driver(self):
        info = inspect_uri(self.uri)
        self.assertEqual(info["engine"], "sqlite")
        self.assertEqual(info["reader"], "native")
        self.assertIsNone(info["driver_error"])

    def test_summarize_error_is_short_and_not_empty(self):
        msg = summarize_error(RuntimeError("boom " * 500))
        self.assertTrue(msg)
        self.assertLess(len(msg), 2500)

    def test_scan_demo_schema(self):
        phases = []
        result = run_db_scan(self.uri, lambda phase, message, pct: phases.append(phase))
        self.assertEqual(result["status"], "success", result)
        tables = result["data"]
        self.assertIn("customers", tables)
        self.assertIn("order_items", tables)
        # FK declarada: addresses.customer_id -> customers.customer_id
        rel = {(r["col"], r["ref_table"], r["ref_col"]) for r in tables["addresses"]["relations"]}
        self.assertIn(("customer_id", "customers", "customer_id"), rel)
        # PK compuesta
        pks = [c["name"] for c in tables["order_items"]["columns"] if c["pk"]]
        self.assertEqual(sorted(pks), ["order_id", "product_id"])
        # tabla sin PK a propósito
        self.assertFalse(any(c["pk"] for c in tables["newsletter_queue"]["columns"]))
        # fases en orden
        self.assertEqual(phases[0], "connect")
        self.assertIn("build", phases)

    def test_finalize_computes_referenced_by_and_meta(self):
        tables = finalize_schema(run_db_scan(self.uri)["data"])
        back = {r["table"] for r in tables["customers"]["referenced_by"]}
        self.assertTrue({"addresses", "orders", "wishlists"} <= back)
        meta = compute_meta(tables)
        self.assertEqual(meta["table_count"], len(tables))
        self.assertEqual(meta["table_count"], meta["related_count"] + meta["orphan_count"])
        self.assertGreaterEqual(meta["no_pk_count"], 1)

    def test_finalize_accepts_legacy_1x_format(self):
        legacy = {"t": {"columns": [{"name": "id", "type": "int", "null": "NO", "is_pk": True}], "relations": []}}
        out = finalize_schema(legacy)
        self.assertTrue(out["t"]["columns"][0]["pk"])
        self.assertFalse(out["t"]["columns"][0]["null"])

    def test_scan_bad_uri_returns_error_not_exception(self):
        result = run_db_scan("sqlite:///no/existe/carpeta/x.db")
        self.assertEqual(result["status"], "error")
        self.assertTrue(result["message"])

    def test_scan_missing_driver_message(self):
        result = run_db_scan("oracle://u:p@h/db")
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
