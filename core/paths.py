"""Rutas de la app, resueltas por sistema operativo.

- Recursos de solo lectura (webui/, CHANGELOG.md, HELP.md): dentro del
  paquete PyInstaller (sys._MEIPASS) o junto al código en desarrollo.
- Datos del usuario (historial, ajustes, logs): una carpeta SIEMPRE
  escribible. En Windows es la misma que usaban las versiones 1.x
  (%LOCALAPPDATA%\\Etch-DB-Mapper), así que el historial existente se
  conserva al actualizar.

Se puede forzar otra carpeta con la variable de entorno ETCH_DATA_DIR
(útil para pruebas, para no tocar el historial real).
"""
import os
import sys
from pathlib import Path

from .version import APP_NAME


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", project_root()))
    return base.joinpath(*parts)


def user_data_dir() -> Path:
    override = os.environ.get("ETCH_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:  # Linux / BSD: XDG
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base
