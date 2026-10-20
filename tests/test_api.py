import tempfile
import threading
import unittest
from pathlib import Path

from core.api import Api
from core.storage import Store


class FakeWindow:
    """Sustituye a la ventana de pywebview: guarda los eventos que la UI recibiría."""

    def __init__(self):
        self.events = []
        self.done = threading.Event()

    def evaluate_js(self, code):
        self.events.append(code)
        if "scan_finished" in code:
            self.done.set()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name))
        self.win = FakeWindow()
        self.api = Api(self.store, self.win)

    def tearDown(self):
        self._tmp.cleanup()

    def test_bootstrap_shape(self):
        b = self.api.bootstrap()
        for key in ("version", "settings", "connections", "data_dir", "warnings"):
            self.assertIn(key, b)

    def test_uri_is_saved_before_any_scan(self):
        r = self.api.save_connection("Mi base", "postgres://u:p@host:5432/db")
        self.assertTrue(r["ok"])
        self.assertTrue(self.store.exists("Mi base"))
        self.assertEqual(self.api.get_connection("Mi base")["uri"], "postgres://u:p@host:5432/db")

    def test_summary_never_leaks_password(self):
        self.api.save_connection("X", "postgres://u:Secreto123@host/db")
        for c in self.api.list_connections():
            self.assertNotIn("Secreto123", str(c))

    def test_validation_errors(self):
        self.assertFalse(self.api.save_connection("", "postgres://u:p@h/db")["ok"])
        self.assertFalse(self.api.save_connection("A", "sin-esquema")["ok"])
        self.assertFalse(self.api.save_connection("A" * 61, "postgres://u:p@h/db")["ok"])

    def test_duplicate_alias_rejected_on_create(self):
        self.api.save_connection("A", "postgres://u:p@h/db")
        self.assertFalse(self.api.save_connection("A", "postgres://u:p@h/db2")["ok"])

    def test_edit_uri_and_rename_in_one_call(self):
        self.api.save_connection("A", "postgres://u:p@h/db")
        r = self.api.save_connection("B", "postgres://u:p@h/otra", previous_alias="A")
        self.assertTrue(r["ok"])
        self.assertFalse(self.store.exists("A"))
        self.assertEqual(self.api.get_connection("B")["uri"], "postgres://u:p@h/otra")

    def test_rename_connection(self):
        self.api.save_connection("A", "postgres://u:p@h/db")
        self.api.save_connection("B", "postgres://u:p@h/db")
        self.assertFalse(self.api.rename_connection("A", "B")["ok"])
        self.assertTrue(self.api.rename_connection("A", "C")["ok"])
        self.assertEqual(sorted(c["alias"] for c in self.api.list_connections()), ["B", "C"])

    def test_demo_scan_end_to_end_emits_events(self):
        self.api.create_demo_connection()
        alias = self.api.list_connections()[0]["alias"]
        self.assertTrue(self.api.start_scan(alias)["ok"])
        self.assertTrue(self.win.done.wait(30), "el escaneo no terminó")
        joined = "\n".join(self.win.events)
        self.assertIn("scan_started", joined)
        self.assertIn("scan_progress", joined)
        schema = self.api.get_schema(alias)
        self.assertTrue(schema["ok"])
        self.assertEqual(schema["status"], "success")
        self.assertGreater(schema["meta"]["table_count"], 10)
        self.assertGreater(schema["meta"]["relation_count"], 10)

    def test_failed_scan_keeps_connection_and_reports_error(self):
        self.api.save_connection("Rota", "sqlite:///no/existe/x.db")
        self.api.start_scan("Rota")
        self.assertTrue(self.win.done.wait(30))
        conn = self.api.list_connections()[0]
        self.assertEqual(conn["status"], "error")
        self.assertTrue(conn["last_error"])
        self.assertTrue(self.store.exists("Rota"))   # la URI NO se pierde

    def test_save_map_state_sanitizes(self):
        self.api.save_connection("A", "sqlite://x.db")
        r = self.api.save_map_state("A", {"positions": {"t": {"x": 1.234, "y": 5}, "bad": {"x": "a"}, "huge": {"x": 1e12, "y": 0}}, "layout": "fcose"})
        self.assertTrue(r["ok"])
        pos = self.store.get("A")["map"]["positions"]
        self.assertEqual(list(pos), ["t"])

    def test_open_external_rejects_non_http(self):
        self.assertFalse(self.api.open_external("file:///C:/Windows/System32/calc.exe")["ok"])
        self.assertFalse(self.api.open_external("javascript:alert(1)")["ok"])

    def test_docs_are_readable(self):
        self.assertIn("Guía", self.api.get_help()["markdown"])
        self.assertIn("Novedades", self.api.get_changelog()["markdown"])

    def test_internal_attributes_are_not_public(self):
        public = [n for n in dir(self.api) if not n.startswith("_")]
        for forbidden in ("store", "window", "lock"):
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
