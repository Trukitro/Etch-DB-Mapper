"""Base de ejemplo (SQLite) para que un usuario nuevo pueda probar la app
sin tener una base propia, y fixture de los tests del scanner.

Es un esquema de tienda online (con unas pocas filas de ejemplo) con claves compuestas, una relación
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


def _seed(con):
    """Datos ficticios y deterministas (sirven para probar el escaneo, el mapa y la copia de datos)."""
    q = con.executemany
    q("INSERT INTO countries VALUES (?, ?)", [("ES", "España"), ("MX", "México"), ("AR", "Argentina"), ("CO", "Colombia")])
    names = ["Ana Torres", "Luis Pérez", "Marta Gil", "Jorge Ruiz", "Lucía Soto", "Pablo Vega", "Elena Mora", "Diego Cruz"]
    countries = ["ES", "MX", "AR", "CO"]
    q("INSERT INTO customers VALUES (?,?,?,?,?,?)", [(i + 1, f"cliente{i + 1}@ejemplo.test", n, None if i % 3 else f"+34 600 000 0{i:02d}",
                                                      f"2026-0{1 + i % 9}-1{i % 9} 10:00:00", countries[i % 4]) for i, n in enumerate(names)])
    q("INSERT INTO addresses VALUES (?,?,?,?,?,?)", [(i + 1, i + 1, f"Calle Ejemplo {10 + i}", ["Madrid", "Ciudad de México", "Rosario", "Bogotá"][i % 4],
                                                      f"{28000 + i}", countries[i % 4]) for i in range(8)])
    q("INSERT INTO categories VALUES (?,?,?)", [(1, "Electrónica", None), (2, "Hogar", None), (3, "Audio", 1), (4, "Cocina", 2), (5, "Juguetes", None)])
    q("INSERT INTO suppliers VALUES (?,?,?,?)", [(1, "Proveedor Uno", "uno@proveedor.test", "ES"), (2, "Proveedor Dos", "dos@proveedor.test", "MX"), (3, "Proveedor Tres", None, "AR")])
    q("INSERT INTO products VALUES (?,?,?,?,?,?,?)", [(i + 1, f"SKU-{1000 + i}", f"Producto {i + 1}", None if i % 2 else f"Descripción del producto {i + 1}",
                                                       round(9.99 + i * 7.5, 2), [3, 4, 5, 1, 2][i % 5], 0 if i == 9 else 1) for i in range(10)])
    q("INSERT INTO product_suppliers VALUES (?,?,?)", [(p, 1 + (p + k) % 3, round(4.5 + p, 2)) for p in range(1, 11) for k in (0, 1) if (p + k) % 5 != 4])
    q("INSERT INTO coupons VALUES (?,?,?,?)", [(1, "BIENVENIDA10", 10, "2026-12-31"), (2, "VERANO20", 20, "2026-09-30"), (3, "AMIGOS5", 5, None)])
    statuses = ["pendiente", "pagado", "enviado", "entregado"]
    q("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", [(i + 1, 1 + i % 8, 1 + i % 8, [None, 1, 3][i % 3], statuses[i % 4], f"2026-03-{1 + i:02d} 12:30:00", round(30 + i * 11.25, 2)) for i in range(12)])
    q("INSERT INTO order_items VALUES (?,?,?,?)", [(o, 1 + (o * 3 + k) % 10, 1 + k, round(9.99 + ((o * 3 + k) % 10) * 7.5, 2)) for o in range(1, 13) for k in (0, 1)])
    q("INSERT INTO payments VALUES (?,?,?,?,?)", [(i, i, ["tarjeta", "transferencia", "efectivo"][i % 3], round(30 + (i - 1) * 11.25, 2), f"2026-03-{i:02d} 13:00:00") for i in range(1, 11)])
    q("INSERT INTO shipments VALUES (?,?,?,?,?,?)", [(i, i, ["Correos", "DHL", None][i % 3], None if i % 3 == 2 else f"TRK{i:06d}", f"2026-03-{i + 1:02d} 09:00:00", None if i % 2 else f"2026-03-{i + 4:02d} 17:00:00") for i in range(1, 9)])
    q("INSERT INTO reviews VALUES (?,?,?,?,?)", [(i, 1 + i % 10, 1 + i % 8, 3 + i % 3, None if i % 4 == 0 else f"Reseña número {i}: muy buen producto.") for i in range(1, 11)])
    q("INSERT INTO wishlists VALUES (?,?,?)", [(c, 1 + (c * 2) % 10, f"2026-02-0{c}") for c in range(1, 9)])
    q("INSERT INTO departments VALUES (?,?)", [(1, "Ventas"), (2, "Logística"), (3, "Soporte")])
    q("INSERT INTO employees VALUES (?,?,?,?,?)", [(1, "Carmen Díaz", 1, None, "2020-01-15"), (2, "Raúl Márquez", 1, 1, "2021-03-01"), (3, "Sofía León", 2, 1, "2022-06-20"),
                                                   (4, "Iván Rojas", 2, 3, "2023-02-10"), (5, "Noa Prieto", 3, 1, "2024-09-05"), (6, "Hugo Sanz", 3, 5, "2025-01-12")])
    q("INSERT INTO audit_log VALUES (?,?,?,?,?)", [(i, f"2026-03-0{i} 08:00:00", ["admin", "sistema", None][i % 3], ["login", "edición", "exportación"][i % 3], None) for i in range(1, 9)])
    q("INSERT INTO app_settings VALUES (?,?)", [("tema", "oscuro"), ("moneda", "EUR"), ("idioma", "es"), ("zona_horaria", "Europe/Madrid")])
    q("INSERT INTO newsletter_queue VALUES (?,?,?)", [(f"cliente{i}@ejemplo.test", "Novedades de marzo", f"2026-03-0{i} 07:00:00") for i in range(1, 6)])


def create_demo_db(path) -> str:
    """Crea (o recrea) la base de ejemplo en `path` y devuelve la URI pydal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        con.executescript(DEMO_SQL)
        _seed(con)
        con.commit()
    finally:
        con.close()
    return "sqlite://" + str(path.resolve()).replace("\\", "/")
