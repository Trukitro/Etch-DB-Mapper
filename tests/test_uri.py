import tempfile
import unittest
from pathlib import Path

from core.demo import create_demo_db
from core.scanner import test_connection
from core.uri import build_uri, odbc_drivers, parse_uri, target_of


class BuildUriTests(unittest.TestCase):
    def test_postgres_basic(self):
        uri = build_uri({"engine": "postgres", "host": "10.1.2.3", "port": "5432", "user": "ana", "password": "x", "database": "mi_db"})
        self.assertEqual(uri, "postgres://ana:x@10.1.2.3:5432/mi_db")

    def test_special_characters_in_credentials_are_encoded(self):
        uri = build_uri({"engine": "mysql", "host": "h", "user": "u@x", "password": "p@ss:w/rd%1!", "database": "d"})
        self.assertNotIn("p@ss", uri)
        f = parse_uri(uri)
        self.assertEqual((f["user"], f["password"]), ("u@x", "p@ss:w/rd%1!"))

    def test_empty_password_and_default_port(self):
        self.assertEqual(build_uri({"engine": "mysql", "host": "h", "user": "u", "database": "d"}), "mysql://u@h/d")

    def test_mssql_driver_and_trust_cert(self):
        uri = build_uri({"engine": "mssql", "host": "srv", "port": "1433", "user": "u", "password": "p", "database": "d",
                         "driver": "ODBC Driver 18 for SQL Server", "trust_cert": True})
        self.assertEqual(uri, "mssql4://u:p@srv:1433/d?DRIVER={ODBC Driver 18 for SQL Server}&TrustServerCertificate=yes")
        f = parse_uri(uri)
        self.assertEqual(f["driver"], "ODBC Driver 18 for SQL Server")
        self.assertTrue(f["trust_cert"])
        self.assertEqual(f["extra"], "")

    def test_scheme_variant_is_preserved(self):
        f = parse_uri("mssql4n://u:p@h:1433/d?DRIVER={SQL Server}")
        self.assertEqual(f["scheme"], "mssql4n")
        self.assertTrue(build_uri(f).startswith("mssql4n://"))

    def test_extra_args_roundtrip(self):
        f = parse_uri("postgres://u:p@h/d?sslmode=require")
        self.assertEqual(f["extra"], "sslmode=require")
        self.assertTrue(build_uri(f).endswith("/d?sslmode=require"))

    def test_sqlite_path(self):
        self.assertEqual(build_uri({"engine": "sqlite", "path": "C:\\datos\\mi base.db"}), "sqlite://C:/datos/mi base.db")
        self.assertEqual(parse_uri("sqlite://C:/datos/x.db")["path"], "C:/datos/x.db")

    def test_ipv6_host(self):
        uri = build_uri({"engine": "postgres", "host": "::1", "user": "u", "database": "d"})
        self.assertEqual(uri, "postgres://u@[::1]/d")
        self.assertEqual(parse_uri(uri)["host"], "::1")

    def test_validation_messages(self):
        for fields in (
            {}, {"engine": "postgres"}, {"engine": "postgres", "host": "h"},
            {"engine": "postgres", "host": "h", "user": "u"},
            {"engine": "postgres", "host": "h", "user": "u", "database": "d", "port": "abc"},
            {"engine": "postgres", "host": "h", "user": "u", "database": "d", "port": "70000"},
            {"engine": "postgres", "host": "a b", "user": "u", "database": "d"},
            {"engine": "sqlite"},
        ):
            with self.assertRaises(ValueError, msg=str(fields)):
                build_uri(fields)

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_uri("oracle://u:p@h/d"))
        self.assertIsNone(parse_uri("sin-esquema"))
        self.assertIsNone(parse_uri("mssql://DSN_SIN_ARROBA"))

    def test_legacy_password_with_raw_at_sign_is_recovered(self):
        f = parse_uri("postgres://u:pa@ss@host:5432/db")
        self.assertEqual((f["password"], f["host"]), ("pa@ss", "host"))

    def test_target_of(self):
        self.assertEqual(target_of("postgres://u:p@h/db"), ("h", 5432))
        self.assertEqual(target_of("mssql4://u:p@h:1444/db"), ("h", 1444))
        self.assertIsNone(target_of("sqlite://x.db"))

    def test_odbc_drivers_returns_list(self):
        self.assertIsInstance(odbc_drivers(), list)


class TestConnectionTests(unittest.TestCase):
    def test_sqlite_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = test_connection(create_demo_db(Path(tmp) / "d.sqlite"))
        self.assertTrue(r["ok"], r)

    def test_unreachable_port_fails_fast_with_clear_message(self):
        r = test_connection("postgres://u:p@127.0.0.1:1/db", timeout=2)
        self.assertFalse(r["ok"])
        self.assertIn("127.0.0.1:1", r["error"])


if __name__ == "__main__":
    unittest.main()
