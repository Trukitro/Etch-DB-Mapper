"""Launcher de Etch-DB-Mapper: abre una ventana pywebview con la UI web
(webui/) y le expone el backend Python (core/api.py).

    python db_manager_app.py            # normal
    python db_manager_app.py --debug    # con DevTools (clic derecho -> Inspeccionar)
    python db_manager_app.py --data-dir C:\\ruta   # otra carpeta de datos (pruebas)
"""
import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from core.api import Api
from core.paths import resource_path
from core.storage import Store
from core.version import APP_NAME, __version__

WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"


def _setup_logging(data_dir, debug):
    handler = RotatingFileHandler(data_dir / "etch.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.addHandler(handler)


def _free_port():
    """Puerto TCP libre elegido por el sistema (evita choques con otras apps)."""
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fatal(message):
    """La app empaquetada no tiene consola: el error se muestra en un diálogo."""
    print(message, file=sys.stderr)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
        except Exception:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {__version__}")
    parser.add_argument("--debug", action="store_true", help="habilita DevTools y logging detallado")
    parser.add_argument("--data-dir", help="carpeta de datos alternativa (historial, ajustes, logs)")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = parser.parse_args(argv)

    store = Store(args.data_dir)
    _setup_logging(store.dir, args.debug)
    log = logging.getLogger("etch")
    log.info("Iniciando %s %s (datos en %s)", APP_NAME, __version__, store.dir)

    index = resource_path("webui", "index.html")
    if not index.exists():
        _fatal(f"No se encontró la interfaz web ({index}). La instalación está incompleta.")
        return 1

    import webview  # import tardío: --version/--help no necesitan cargarlo

    api = Api(store)
    window = webview.create_window(
        APP_NAME, url=str(index), js_api=api,
        width=1360, height=860, min_size=(1000, 640), background_color="#0a0f1a",
    )
    api._bind(window)

    # En Windows se exige WebView2 (Chromium). Sin esto pywebview caería en
    # el motor legacy de IE, donde la UI se vería rota.
    gui = "edgechromium" if sys.platform == "win32" else None
    # pywebview sirve los archivos locales por un servidor HTTP interno. Con
    # private_mode=False lo ata al puerto FIJO 42001, que otras apps pywebview
    # comparten: la ventana terminaba mostrando la página de otra aplicación.
    # Modo privado = puerto libre al azar y sin caché compartida (la app guarda
    # todo en su carpeta de datos, no usa cookies ni localStorage).
    try:
        webview.start(debug=args.debug, gui=gui, private_mode=True, http_port=_free_port())
    except Exception as e:
        log.exception("No se pudo iniciar la ventana")
        _fatal(
            f"No se pudo abrir la ventana de {APP_NAME}.\n\n{e}\n\n"
            f"En Windows se necesita el runtime Microsoft Edge WebView2:\n{WEBVIEW2_URL}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
