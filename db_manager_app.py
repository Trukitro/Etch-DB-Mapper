import os
import sys
from ui.main_ui import DBMapperUI
from core.storage import load_json_history

def main():
    # resource_path: assets estáticos de solo lectura (empaquetados dentro
    # del .exe en modo onefile).
    # storage_path: historial de usuario, tiene que vivir en una carpeta
    # donde el usuario pueda escribir SIEMPRE. Si el .exe corre desde
    # "Program Files" (instalación normal con el instalador), escribir al
    # lado del .exe falla con PermissionError - Windows protege esa carpeta.
    if getattr(sys, 'frozen', False):
        resource_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        appdata_dir = os.path.join(
            os.getenv("LOCALAPPDATA") or os.path.expanduser("~"),
            "Etch-DB-Mapper",
        )
        os.makedirs(appdata_dir, exist_ok=True)
        storage_path = os.path.join(appdata_dir, "db_maps.json")
    else:
        resource_path = os.path.dirname(os.path.abspath(__file__))
        storage_path = os.path.join(resource_path, "db_maps.json")

    icon_path = os.path.join(resource_path, "favicon.ico")
    logo_path = os.path.join(resource_path, "etch_db_logo.png")

    # 1. Cargar Datos
    history = load_json_history(storage_path)

    # 2. Arrancar UI
    app = DBMapperUI(history, storage_path, icon_path, logo_path)
    app.mainloop()

if __name__ == "__main__":
    main()