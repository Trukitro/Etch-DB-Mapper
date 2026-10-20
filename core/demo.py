"""Base de ejemplo (SQLite) para que un usuario nuevo pueda probar la app
sin tener una base propia, y fixture de los tests del scanner.

Es un esquema de tienda online con claves compuestas, una relación
autorreferencial (employees.manager_id) y algunas tablas huérfanas a
propósito, para que el mapa y el dashboard tengan algo que mostrar.
"""
import sqlite3
from pathlib import Path

DEMO_ALIAS = "Demo - Tienda online"

DEMO_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE countries      (country_code TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE customers      (customer_id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL,
                             phone TEXT, created_at TEXT NOT NULL, country_code TEXT REFERENCES countries(country_code));
CREATE TABLE addresses      (address_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                             line1 TEXT NOT NULL, city TEXT NOT NULL, postal_code TEXT, country_code TEXT REFERENCES countries(country_code));
CREATE TABLE categories     (category_id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_id INTEGER REFERENCES categories(category_id));
CREATE TABLE suppliers      (supplier_id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact_email TEXT, country_code TEXT REFERENCES countries(country_code));
CREATE TABLE products       (product_id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT,
                             price NUMERIC NOT NULL, category_id INTEGER REFERENCES categories(category_id), active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE product_suppliers (product_id INTEGER NOT NULL REFERENCES products(product_id),
                             supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id), cost NUMERIC,
                             PRIMARY KEY (product_id, supplier_id));
CREATE TABLE coupons        (coupon_id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, percent_off INTEGER NOT NULL, expires_at TEXT);
CREATE TABLE orders         (order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                             ship_address_id INTEGER REFERENCES addresses(address_id), coupon_id INTEGER REFERENCES coupons(coupon_id),
                             status TEXT NOT NULL, placed_at TEXT NOT NULL, total NUMERIC NOT NULL);
CREATE TABLE order_items    (order_id INTEGER NOT NULL REFERENCES orders(order_id), product_id INTEGER NOT NULL REFERENCES products(product_id),
                             quantity INTEGER NOT NULL, unit_price NUMERIC NOT NULL, PRIMARY KEY (order_id, product_id));
CREATE TABLE payments       (payment_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(order_id),
                             method TEXT NOT NULL, amount NUMERIC NOT NULL, paid_at TEXT);
CREATE TABLE shipments      (shipment_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(order_id),
                             carrier TEXT, tracking_code TEXT, shipped_at TEXT, delivered_at TEXT);
CREATE TABLE reviews        (review_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(product_id),
                             customer_id INTEGER NOT NULL REFERENCES customers(customer_id), rating INTEGER NOT NULL, body TEXT);
CREATE TABLE wishlists      (customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                             product_id INTEGER NOT NULL REFERENCES products(product_id), added_at TEXT,
                             PRIMARY KEY (customer_id, product_id));
CREATE TABLE departments    (department_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE employees      (employee_id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, department_id INTEGER REFERENCES departments(department_id),
                             manager_id INTEGER REFERENCES employees(employee_id), hired_at TEXT);
-- Huérfanas a propósito (sin relaciones declaradas):
CREATE TABLE audit_log      (id INTEGER PRIMARY KEY, happened_at TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, detail TEXT);
CREATE TABLE app_settings   (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE newsletter_queue (email TEXT NOT NULL, subject TEXT, queued_at TEXT);   -- sin clave primaria, a propósito
"""


def create_demo_db(path) -> str:
    """Crea (o recrea) la base de ejemplo en `path` y devuelve la URI pydal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        con.executescript(DEMO_SQL)
        con.commit()
    finally:
        con.close()
    return "sqlite://" + str(path.resolve()).replace("\\", "/")
