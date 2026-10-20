import json
import tempfile
import unittest
from pathlib import Path

from core.storage import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_put_get_persist_roundtrip(self):
        s = Store(self.dir)
        s.put("A", {"uri": "sqlite://a.db", "data": {}})
        s2 = Store(self.dir)
        self.assertEqual(s2.get("A")["uri"], "sqlite://a.db")
        self.assertTrue(s2.get("A")["id"])

    def test_rename_keeps_id_and_rejects_duplicates(self):
        s = Store(self.dir)
        s.put("A", {"uri": "x://1"})
        s.put("B", {"uri": "x://2"})
        old_id = s.get("A")["id"]
        s.rename("A", "C")
        self.assertEqual(s.get("C")["id"], old_id)
        self.assertFalse(s.exists("A"))
        with self.assertRaises(ValueError):
            s.rename("C", "B")
        self.assertEqual(s.alias_by_id(old_id), "C")

    def test_legacy_file_without_ids_gets_ids(self):
        (self.dir / "db_maps.json").write_text(json.dumps({"Old": {"uri": "mssql4://u:p@h/db", "data": {}}}), encoding="utf-8")
        s = Store(self.dir)
        self.assertTrue(s.get("Old")["id"])

    def test_corrupt_file_is_backed_up_and_reported(self):
        (self.dir / "db_maps.json").write_text("{ esto no es json", encoding="utf-8")
        s = Store(self.dir)
        self.assertEqual(s.aliases(), [])
        self.assertTrue(s.load_warnings)
        self.assertTrue(list(self.dir.glob("db_maps.json.corrupt-*")))

    def test_settings_only_accept_known_keys_and_types(self):
        s = Store(self.dir)
        out = s.patch_settings({"theme": "light", "sidebar_collapsed": "no-es-bool", "inventada": 1})
        self.assertEqual(out["theme"], "light")
        self.assertFalse(out["sidebar_collapsed"])
        self.assertNotIn("inventada", out)
        self.assertEqual(Store(self.dir).settings()["theme"], "light")

    def test_no_tmp_file_left_after_write(self):
        s = Store(self.dir)
        s.put("A", {"uri": "x://1"})
        self.assertFalse(list(self.dir.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
