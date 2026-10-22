import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

from core.scanner import scrub_secrets, summarize_error
from core.secrets import NullProtector, SecretError, WindowsProtector, get_protector
from core.storage import Store


class FakeProtector:
    """Cifrado de juguete reversible (solo para probar la lógica del Store en cualquier SO)."""
    name, available, label = "fake", True, "fake"

    def protect(self, text):
        return "fake:" + base64.b64encode(text[::-1].encode()).decode()

    def unprotect(self, token):
        if not token.startswith("fake:"):
            raise SecretError("formato")
        return base64.b64decode(token[5:]).decode()[::-1]


class BrokenProtector(FakeProtector):
    def unprotect(self, token):
        raise SecretError("otro usuario")


class StoreEncryptionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def raw(self):
        return (self.dir / "db_maps.json").read_text(encoding="utf-8")

    def test_password_never_reaches_disk_in_clear(self):
        s = Store(self.dir, FakeProtector())
        s.put("A", {"uri": "postgres://u:SuperSecreta@h:5432/db"})
        self.assertNotIn("SuperSecreta", self.raw())
        self.assertIn("uri_enc", self.raw())
        self.assertEqual(s.get("A")["uri"], "postgres://u:SuperSecreta@h:5432/db")      # en memoria sí
        self.assertEqual(Store(self.dir, FakeProtector()).get("A")["uri"], "postgres://u:SuperSecreta@h:5432/db")

    def test_update_uri_reseals(self):
        s = Store(self.dir, FakeProtector())
        s.put("A", {"uri": "postgres://u:uno@h/db"})
        s.update("A", uri="postgres://u:dos@h/db")
        self.assertNotIn("dos", self.raw())
        self.assertEqual(s.get("A")["uri"], "postgres://u:dos@h/db")

    def test_uri_without_password_is_left_as_is(self):
        s = Store(self.dir, FakeProtector())
        s.put("L", {"uri": "sqlite://C:/datos/x.db"})
        self.assertNotIn("uri_enc", json.loads(self.raw())["L"])
        self.assertIn("sqlite://C:/datos/x.db", self.raw())

    def test_legacy_plaintext_is_migrated_on_load(self):
        (self.dir / "db_maps.json").write_text(json.dumps({"Old": {"uri": "mssql4://u:ClaveVieja@h/db", "data": {}}}), encoding="utf-8")
        s = Store(self.dir, FakeProtector())
        self.assertNotIn("ClaveVieja", self.raw())
        self.assertEqual(s.get("Old")["uri"], "mssql4://u:ClaveVieja@h/db")
        st = s.security_status()
        self.assertEqual((st["connections_with_password"], st["encrypted"]), (1, 1))

    def test_undecryptable_secret_is_flagged_not_crashing(self):
        Store(self.dir, FakeProtector()).put("A", {"uri": "postgres://u:x@h/db"})
        got = Store(self.dir, BrokenProtector()).get("A")
        self.assertTrue(got["secret_error"])
        self.assertNotIn(":x@", got["uri"])

    def test_without_protector_nothing_is_claimed_encrypted(self):
        s = Store(self.dir, NullProtector())
        s.put("A", {"uri": "postgres://u:x@h/db"})
        st = s.security_status()
        self.assertFalse(st["available"])
        self.assertEqual(st["encrypted"], 0)

    def test_delete_removes_history_file(self):
        s = Store(self.dir, FakeProtector())
        s.put("A", {"uri": "sqlite://x.db"})
        cid = s.get("A")["id"]
        s.add_snapshot(cid, {"t": {"columns": [], "relations": []}}, "2026-01-01 00:00:00")
        self.assertTrue(any((self.dir / "snapshots").glob("*.json")))
        s.delete("A")
        self.assertFalse(any((self.dir / "snapshots").glob("*.json")))


@unittest.skipUnless(sys.platform == "win32", "DPAPI solo existe en Windows")
class WindowsDpapiTests(unittest.TestCase):
    def test_roundtrip_and_ciphertext_hides_the_secret(self):
        p = WindowsProtector()
        token = p.protect("postgres://u:MuySecreta!@h/db")
        self.assertNotIn("MuySecreta", token)
        self.assertEqual(p.unprotect(token), "postgres://u:MuySecreta!@h/db")

    def test_tampered_token_raises(self):
        p = WindowsProtector()
        with self.assertRaises(SecretError):
            p.unprotect("dpapi:v1:AAAA")

    def test_get_protector_is_dpapi(self):
        self.assertEqual(get_protector().name, "dpapi")


class ScrubTests(unittest.TestCase):
    def test_connection_strings_and_uris_are_scrubbed(self):
        msg = scrub_secrets("fallo SERVER=h;UID=u;PWD=Sup3r!;DRIVER={x} en postgres://bob:hunter2@h/db")
        self.assertNotIn("Sup3r", msg)
        self.assertNotIn("hunter2", msg)

    def test_summarize_error_skips_postgres_context_lines(self):
        err = RuntimeError("\n".join(['relation "prueba" does not exist', "LINE 1: SELECT COUNT(*) FROM prueba", "                              ^", ""]))
        self.assertEqual(summarize_error(err), 'relation "prueba" does not exist')

    def test_summarize_error_scrubs(self):
        self.assertNotIn("zzz", summarize_error(RuntimeError("x\nPassword=zzz;")))


class LogScrubTests(unittest.TestCase):
    def test_log_file_never_contains_passwords_even_in_tracebacks(self):
        import logging
        from core.logs import SecretScrubFilter
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.log"
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.addFilter(SecretScrubFilter())
            log = logging.getLogger("etch.test.scrub")
            log.addHandler(handler)
            log.setLevel(logging.INFO)
            log.info("conectando a %s", "postgres://bob:hunter2@h/db")
            try:
                raise RuntimeError("fallo SERVER=h;PWD=Sup3r!;DRIVER={x}")
            except RuntimeError:
                log.exception("Escaneo falló")
            handler.close()
            log.removeHandler(handler)
            text = path.read_text(encoding="utf-8")
        self.assertNotIn("hunter2", text)
        self.assertNotIn("Sup3r", text)
        self.assertIn("Escaneo falló", text)


if __name__ == "__main__":
    unittest.main()
