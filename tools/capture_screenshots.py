"""Genera las capturas de docs/images/ con la app REAL (Windows).

Usa solo datos de demostración creados acá (una tienda con claves foráneas y un
ERP "antiguo" sin ellas), en una carpeta de datos temporal: nunca toca tus
conexiones ni el historial reales. Las capturas se hacen con PrintWindow sobre
la ventana de ESTE proceso (no confunde otras ventanas abiertas).

    python tools/capture_screenshots.py
"""
import ctypes
import json
import os
import shutil
import sqlite3
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
DATA = Path("C:/etch-demo")           # ruta neutra: se ve en el Resumen ("Destino")
sys.path.insert(0, str(ROOT))

import webview  # noqa: E402
from PIL import Image  # noqa: E402

from core.api import Api  # noqa: E402
from core.demo import create_demo_db  # noqa: E402
from core.storage import Store  # noqa: E402

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32

LEGACY_SQL = """
CREATE TABLE Clientes (ClienteID INTEGER PRIMARY KEY, Nombre TEXT NOT NULL, Email TEXT, CiudadID INTEGER);
CREATE TABLE Ciudades (CiudadID INTEGER PRIMARY KEY, Nombre TEXT, PaisID INTEGER);
CREATE TABLE Paises (PaisID INTEGER PRIMARY KEY, Nombre TEXT);
CREATE TABLE Vendedores (VendedorID INTEGER PRIMARY KEY, Nombre TEXT, Comision REAL);
CREATE TABLE Pedidos (PedidoID INTEGER PRIMARY KEY, ClienteID INTEGER, VendedorID INTEGER, Fecha TEXT, Total REAL);
CREATE TABLE Productos (ProductoID INTEGER PRIMARY KEY, Nombre TEXT, CategoriaID INTEGER, Precio REAL);
CREATE TABLE Categorias (CategoriaID INTEGER PRIMARY KEY, Nombre TEXT);
CREATE TABLE PedidoDetalle (PedidoID INTEGER, ProductoID INTEGER, Cantidad INTEGER, PRIMARY KEY (PedidoID, ProductoID));
CREATE TABLE Facturas (FacturaID INTEGER PRIMARY KEY, PedidoID INTEGER, Monto REAL);
CREATE TABLE Pagos (PagoID INTEGER PRIMARY KEY, FacturaID INTEGER, Monto REAL, Fecha TEXT);
CREATE TABLE Configuracion (Clave TEXT PRIMARY KEY, Valor TEXT);
CREATE TABLE LogErrores (LogID INTEGER PRIMARY KEY, Mensaje TEXT, Fecha TEXT);
"""


def window_of_this_process():
    found = []
    pid = os.getpid()
    enum = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
        return True

    user32.EnumWindows(enum(cb), 0)
    return found[0] if found else None


def shot(name):
    hwnd = window_of_this_process()
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("x", wintypes.LONG), ("y", wintypes.LONG), ("c", wintypes.DWORD), ("i", wintypes.DWORD)]

    bi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(OUT / f"{name}.png", optimize=True)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    print("captura", name, img.size)


def js(window, code, wait=0.8):
    r = window.evaluate_js(code)
    time.sleep(wait)
    return r


def export_report(api, alias):
    """Informe HTML interactivo + captura con Edge sin ventana (si Edge está instalado)."""
    import subprocess
    r = api.export_docs(alias, "html")
    html_path = DATA / "informe.html"
    html_path.write_text(r["content"], encoding="utf-8")
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(exe):
            OUT.mkdir(parents=True, exist_ok=True)
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--screenshot={OUT / '13-informe-html.png'}",
                            "--window-size=1360,1000", "--virtual-time-budget=6000", html_path.as_uri()], check=False, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("captura 13-informe-html")
            return
    print("Edge no encontrado: sin captura del informe")


def script(window, api):
    try:
        time.sleep(3.5)
        js(window, "Etch.state.settings.theme='dark'; Etch.applyTheme(); Etch.go('home')", 0.8)
        shot("01-inicio")

        # --- tienda con claves foráneas (v1) ---
        api.create_demo_connection()
        demo_alias = [c["alias"] for c in api.list_connections()][0]
        js(window, "Etch.refreshConnections().then(()=>{Etch.selectConnection(%s); Etch.scan(%s);})" % (json.dumps(demo_alias), json.dumps(demo_alias)), 4)
        # --- ERP antiguo sin claves foráneas ---
        legacy = DATA / "demo" / "erp_antiguo.sqlite"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        if legacy.exists():
            legacy.unlink()
        con = sqlite3.connect(legacy)
        con.executescript(LEGACY_SQL)
        con.commit()
        con.close()
        api.save_connection("ERP antiguo (sin FKs)", "sqlite://" + str(legacy).replace("\\", "/"))
        js(window, "Etch.refreshConnections().then(()=>Etch.scan('ERP antiguo (sin FKs)'))", 4)

        # --- documentación de ejemplo (notas, etiquetas, responsables) ---
        notes = {
            "customers": ("Personas y empresas que compran en la tienda. Un cliente puede tener varias direcciones.", "Ventas", ["core", "clientes"]),
            "orders": ("Pedidos confirmados. Cada pedido pertenece a un cliente y tiene uno o más artículos.", "Operaciones", ["core", "pedidos"]),
            "products": ("Catálogo de productos a la venta.", "Catálogo", ["catálogo"]),
            "payments": ("Cobros asociados a un pedido (tarjeta, transferencia).", "Finanzas", ["finanzas"]),
        }
        for table, (note, owner, tags) in notes.items():
            api.save_annotation(demo_alias, table, None, {"note": note, "owner": owner, "tags": tags})
        api.save_annotation(demo_alias, "customers", "email", {"note": "Correo único: se usa como usuario de acceso."})
        api.save_annotation(demo_alias, "orders", "status", {"note": "pendiente, pagado, enviado o cancelado."})
        # las notas se guardaron por la API (no por la UI): se descarta el esquema en caché para releerlas
        js(window, "Etch.state.schema = null; Etch.state.schemaAlias = null; Etch.selectConnection(%s); Etch.go('overview')" % json.dumps(demo_alias), 1.6)
        shot("02-resumen")
        js(window, "Etch.go('explorer',{table:'orders'})", 1.2)
        shot("03-explorador")
        js(window, "Etch.go('explorer',{table:'customers'})", 1.2)
        shot("11-documentacion")
        js(window, "Etch.go('paths',{from:'order_items'}); setTimeout(()=>{const t=document.querySelector('[aria-label=\"Tabla de destino\"]'); t.value='customers'; t.dispatchEvent(new Event('change'));}, 400)", 1.8)
        shot("12-rutas")
        export_report(api, demo_alias)

        # --- migración (fase 1): script para SQL Server ---
        js(window, "Etch.go('migrate'); setTimeout(()=>{document.querySelectorAll('.recent .card')[1].click(); setTimeout(()=>{[...document.querySelectorAll('.btn.primary')].find(b=>b.textContent.includes('Generar')).click();}, 300);}, 500)", 2.8)
        shot("14-migracion")
        js(window, "document.querySelectorAll('details.diff-table')[0].open = true; document.querySelector('pre.sql').scrollIntoView({block:'start'}); window.scrollBy(0,-10); document.getElementById('view').scrollTop = document.querySelector('pre.sql').offsetTop - 90", 1.0)
        shot("15-migracion-script")

        # --- migración fase 2: copiar datos a una base vacía (SQLite de destino) ---
        dest_alias = "Destino vacío (SQLite)"
        dest = DATA / "demo" / "destino_copia.sqlite"
        api.save_connection(dest_alias, "sqlite://" + str(dest).replace("\\", "/"))
        js(window, "Etch.refreshConnections().then(()=>{Etch.selectConnection(%s); Etch.go('migrate');})" % json.dumps(demo_alias), 1.5)
        js(window, "[...document.querySelectorAll('.page .tab')].find(b=>b.textContent.includes('Copiar datos')).click()", 0.8)
        js(window, "const s=document.querySelector('.page select'); s.value=%s; s.dispatchEvent(new Event('change')); setTimeout(()=>[...document.querySelectorAll('.btn.primary')].find(b=>b.textContent.includes('Revisar')).click(), 300)" % json.dumps(dest_alias), 3.0)
        js(window, "document.getElementById('view').scrollTop = 0", 0.4)
        shot("16-copia-plan")
        plan = api.preflight_copy(demo_alias, dest_alias)
        api.start_copy(plan["token"], dest_alias)
        time.sleep(4)
        js(window, "const v=document.getElementById('view'); v.scrollTop = v.scrollHeight", 0.8)
        shot("17-copia-resultado")
        js(window, "Etch.go('map')", 2.5)
        shot("04-mapa")

        # --- relaciones probables ---
        js(window, "Etch.selectConnection('ERP antiguo (sin FKs)'); Etch.go('overview')", 1.2)
        shot("05-relaciones-probables-resumen")
        js(window, "Etch.saveSetting('map_show_inferred', true); Etch.go('map')", 2.8)
        shot("06-mapa-relaciones-probables")

        # --- cambios entre escaneos: se altera la tienda y se reescanea ---
        db = DATA / "demo" / "tienda.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE loyalty_cards (card_id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(customer_id), points INTEGER)")
        con.execute("ALTER TABLE orders ADD COLUMN coupon_code TEXT")
        con.execute("DROP TABLE newsletter_queue")
        con.commit()
        con.close()
        js(window, "Etch.selectConnection(%s); Etch.scan(%s)" % (json.dumps(demo_alias), json.dumps(demo_alias)), 4)
        js(window, "Etch.go('changes')", 2)
        js(window, "document.querySelectorAll('.toast').forEach(t=>t.remove())", 0.3)
        shot("07-cambios")

        # --- asistente de conexión y preferencias ---
        js(window, "Etch.go('home'); Etch.dialogs.connection()", 1.5)
        js(window, """(function(){const set=(l,v)=>{const el=document.querySelector('.modal [aria-label="'+l+'"]'); el.value=v; el.dispatchEvent(new Event('input',{bubbles:true}));};
          document.querySelector('.modal input.input').value='Ventas (producción)'; set('Servidor','db.ejemplo.com'); set('Base de datos','ventas'); set('Usuario','analista'); set('Contrase\\u00f1a','ejemplo-no-real');})()""", 1.0)
        shot("08-asistente-conexion")
        # una conexión con contraseña (ficticia) para mostrar el cifrado en Preferencias
        api.save_connection("Ventas (ejemplo)", "postgres://analista:ejemplo-no-real@db.ejemplo.com:5432/ventas")
        js(window, "Etch.refreshConnections().then(()=>Etch.renderChrome()); document.querySelector('.modal header .btn').click(); Etch.dialogs.preferences()", 1.5)
        shot("09-preferencias")
        js(window, "document.querySelector('.modal footer .btn').click(); Etch.go('help')", 1.2)
        shot("10-ayuda")
    except Exception as e:  # noqa: BLE001
        print("ERROR en la captura:", repr(e))
    finally:
        window.destroy()


def main():
    if DATA.exists():
        shutil.rmtree(DATA, ignore_errors=True)
    store = Store(DATA)
    api = Api(store)
    window = webview.create_window("Etch-DB-Mapper", url=str(ROOT / "webui" / "index.html"), js_api=api, width=1360, height=860)
    api._bind(window)
    threading.Thread(target=script, args=(window, api), daemon=True).start()
    webview.start(gui="edgechromium", private_mode=True)
    shutil.rmtree(DATA, ignore_errors=True)


if __name__ == "__main__":
    main()
