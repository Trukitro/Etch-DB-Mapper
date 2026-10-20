"""Persistencia local: conexiones guardadas (db_maps.json) y ajustes
(settings.json).

- Escritura atómica (archivo temporal + os.replace): un cierre brusco o un
  corte de luz no deja el historial a medio escribir.
- Si un JSON está corrupto no se pierde en silencio: se copia a
  *.corrupt-<fecha> y la app arranca vacía avisando.
- Cada conexión tiene un `id` estable (uuid). El alias (la clave visible)
  se puede renombrar; el id no cambia, así un escaneo en curso sigue
  sabiendo a qué conexión pertenece.

El formato de db_maps.json es compatible con las versiones 1.x.
"""
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from .paths import user_data_dir

DEFAULT_SETTINGS = {
    "theme": "dark",              # dark | light | system
    "sidebar_collapsed": False,
    "map_layout": "fcose",
    "map_include_orphans": False,
    "last_alias": "",             # última conexión abierta (se reabre al iniciar)
    "seen_version": "",           # última versión cuyas novedades vio el usuario
}


class Store:
    def __init__(self, data_dir=None):
        self.dir = Path(data_dir) if data_dir else user_data_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self._conn_path = self.dir / "db_maps.json"
        self._set_path = self.dir / "settings.json"
        self._lock = threading.RLock()
        self.load_warnings: list[str] = []

        self._conns: dict = self._read(self._conn_path)
        self._settings: dict = {**DEFAULT_SETTINGS, **self._read(self._set_path)}
        if self._ensure_ids():
            self._write(self._conn_path, self._conns)

    # ---------- archivos ----------
    def _read(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("el JSON raíz no es un objeto")
            return data
        except (json.JSONDecodeError, OSError, ValueError) as e:
            backup = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
            try:
                shutil.copy2(path, backup)
            except OSError:
                backup = None
            self.load_warnings.append(
                f"No se pudo leer {path.name} ({e}). "
                + (f"Se guardó una copia en {backup.name} y se empezó vacío." if backup else "Se empezó vacío.")
            )
            return {}

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _ensure_ids(self) -> bool:
        changed = False
        for entry in self._conns.values():
            if isinstance(entry, dict) and not entry.get("id"):
                entry["id"] = uuid.uuid4().hex
                changed = True
        return changed

    # ---------- conexiones ----------
    def aliases(self) -> list[str]:
        with self._lock:
            return sorted(self._conns.keys(), key=str.lower)

    def get(self, alias: str):
        """Devuelve la entrada (NO la modifiques: usá put/update)."""
        with self._lock:
            return self._conns.get(alias)

    def exists(self, alias: str) -> bool:
        with self._lock:
            return alias in self._conns

    def alias_by_id(self, conn_id: str):
        with self._lock:
            for alias, entry in self._conns.items():
                if entry.get("id") == conn_id:
                    return alias
        return None

    def put(self, alias: str, entry: dict) -> None:
        with self._lock:
            entry.setdefault("id", uuid.uuid4().hex)
            self._conns[alias] = entry
            self._write(self._conn_path, self._conns)

    def update(self, alias: str, **fields) -> None:
        with self._lock:
            self._conns[alias].update(fields)
            self._write(self._conn_path, self._conns)

    def rename(self, old: str, new: str) -> None:
        with self._lock:
            if old not in self._conns:
                raise KeyError(old)
            if new != old and new in self._conns:
                raise ValueError(f"Ya existe una conexión llamada '{new}'.")
            entry = self._conns.pop(old)
            self._conns[new] = entry
            self._write(self._conn_path, self._conns)

    def delete(self, alias: str) -> None:
        with self._lock:
            self._conns.pop(alias, None)
            self._write(self._conn_path, self._conns)

    # ---------- ajustes ----------
    def settings(self) -> dict:
        with self._lock:
            return dict(self._settings)

    def patch_settings(self, patch: dict) -> dict:
        with self._lock:
            for key, value in patch.items():
                if key in DEFAULT_SETTINGS and isinstance(value, type(DEFAULT_SETTINGS[key])):
                    self._settings[key] = value
            self._write(self._set_path, self._settings)
            return dict(self._settings)
