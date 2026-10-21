"""Persistencia local: conexiones guardadas (db_maps.json), ajustes
(settings.json) e historial de versiones del esquema (snapshots/).

- Escritura atómica (archivo temporal + os.replace): un cierre brusco o un
  corte de luz no deja el historial a medio escribir.
- Si un JSON está corrupto no se pierde en silencio: se copia a
  *.corrupt-<fecha> y la app arranca vacía avisando.
- Cada conexión tiene un `id` estable (uuid). El alias (la clave visible)
  se puede renombrar; el id no cambia, así un escaneo en curso sigue
  sabiendo a qué conexión pertenece.
- Las contraseñas no se guardan en claro: si hay un protector disponible
  (Windows DPAPI) la URI completa se cifra en `uri_enc` y en `uri` queda solo
  la versión con la contraseña oculta. `get()` devuelve la URI descifrada en
  memoria; en disco nunca está.

El formato de db_maps.json es compatible con las versiones 1.x (las URI sin
contraseña, como SQLite, se siguen guardando tal cual).
"""
import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from .paths import user_data_dir
from .secrets import SecretError, get_protector
from .uri import has_password, mask_uri

DEFAULT_SETTINGS = {
    "theme": "dark",              # dark | light | system
    "sidebar_collapsed": False,
    "map_layout": "fcose",
    "map_include_orphans": False,
    "map_show_inferred": False,   # dibujar relaciones inferidas por nombre en el mapa
    "last_alias": "",             # última conexión abierta (se reabre al iniciar)
    "seen_version": "",           # última versión cuyas novedades vio el usuario
    "check_updates": True,        # consultar GitHub (como máximo 1 vez al día) por versiones nuevas
    "last_update_check": "",      # ISO de la última consulta
}

MAX_SNAPSHOTS = 8


def compact_schema(tables: dict) -> dict:
    """Esquema normalizado -> forma compacta para guardar/comparar:
    {tabla: {"c": [[col, tipo, nullable, pk]], "r": [[col, tabla_ref, col_ref]]}}."""
    out = {}
    for name, t in (tables or {}).items():
        out[name] = {
            "c": [[c.get("name"), c.get("type", ""), bool(c.get("null")), bool(c.get("pk"))] for c in t.get("columns", [])],
            "r": [[r.get("col"), r.get("ref_table"), r.get("ref_col")] for r in t.get("relations", [])],
        }
    return out


def _digest(compact: dict) -> str:
    return hashlib.sha1(json.dumps(compact, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class Store:
    def __init__(self, data_dir=None, protector=None):
        self.dir = Path(data_dir) if data_dir else user_data_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self._conn_path = self.dir / "db_maps.json"
        self._set_path = self.dir / "settings.json"
        self._snap_dir = self.dir / "snapshots"
        self._lock = threading.RLock()
        self.load_warnings: list[str] = []
        self.protector = protector if protector is not None else get_protector()

        self._conns: dict = self._read(self._conn_path)
        self._settings: dict = {**DEFAULT_SETTINGS, **self._read(self._set_path)}
        changed = self._ensure_ids()
        changed = self._migrate_plaintext_passwords() or changed
        if changed:
            self._write(self._conn_path, self._conns)

    # ---------- archivos ----------
    def _read(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
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

    # ---------- contraseñas ----------
    def _seal(self, entry: dict) -> bool:
        """Cifra entry['uri'] si tiene contraseña y hay protector. Devuelve si cambió algo."""
        uri = entry.get("uri") or ""
        if not (self.protector.available and has_password(uri)):
            entry.pop("uri_enc", None)
            return False
        entry["uri_enc"] = self.protector.protect(uri)
        entry["uri"] = mask_uri(uri)
        return True

    def _migrate_plaintext_passwords(self) -> bool:
        """URI guardadas en claro por versiones anteriores -> cifradas."""
        if not self.protector.available:
            return False
        changed = False
        for entry in self._conns.values():
            if isinstance(entry, dict) and not entry.get("uri_enc") and has_password(entry.get("uri") or ""):
                changed = self._seal(entry) or changed
        return changed

    def _open(self, entry: dict):
        """Entrada con la URI real en memoria (copia) o marcada con secret_error."""
        if not entry or not entry.get("uri_enc"):
            return entry
        try:
            return {**entry, "uri": self.protector.unprotect(entry["uri_enc"])}
        except SecretError:
            return {**entry, "secret_error": True}   # 'uri' queda con la contraseña oculta

    def security_status(self) -> dict:
        with self._lock:
            with_pw = [e for e in self._conns.values() if e.get("uri_enc") or has_password(e.get("uri") or "")]
            return {
                "name": self.protector.name, "available": self.protector.available, "label": self.protector.label,
                "connections_with_password": len(with_pw),
                "encrypted": sum(1 for e in with_pw if e.get("uri_enc")),
            }

    # ---------- conexiones ----------
    def aliases(self) -> list[str]:
        with self._lock:
            return sorted(self._conns.keys(), key=str.lower)

    def get(self, alias: str):
        """Devuelve la entrada (NO la modifiques: usá put/update). Si tiene
        contraseña cifrada es una copia con la URI descifrada."""
        with self._lock:
            return self._open(self._conns.get(alias))

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
            self._seal(entry)
            self._conns[alias] = entry
            self._write(self._conn_path, self._conns)

    def update(self, alias: str, **fields) -> None:
        with self._lock:
            entry = self._conns[alias]
            entry.update(fields)
            if "uri" in fields:
                entry.pop("uri_enc", None)
                self._seal(entry)
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
            entry = self._conns.pop(alias, None)
            self._write(self._conn_path, self._conns)
            if entry and entry.get("id"):
                try:
                    (self._snap_dir / f"{entry['id']}.json").unlink()
                except OSError:
                    pass

    # ---------- historial de versiones del esquema ----------
    def _snap_path(self, conn_id: str) -> Path:
        return self._snap_dir / f"{conn_id}.json"

    def _load_versions(self, conn_id: str) -> list:
        path = self._snap_path(conn_id)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("versions", []) if isinstance(data, dict) else []
        except (json.JSONDecodeError, OSError):
            return []

    def add_snapshot(self, conn_id: str, tables: dict, at: str):
        """Registra el esquema de un escaneo. Si es idéntico a la última versión
        solo se actualiza `last_seen`. Devuelve (version_nueva: bool, version_anterior | None)."""
        compact = compact_schema(tables)
        digest = _digest(compact)
        with self._lock:
            versions = self._load_versions(conn_id)
            if versions and versions[0].get("hash") == digest:
                versions[0]["last_seen"] = at
                is_new, previous = False, (versions[1] if len(versions) > 1 else None)
            else:
                previous = versions[0] if versions else None
                versions.insert(0, {"at": at, "last_seen": at, "hash": digest, "tables": compact})
                versions = versions[:MAX_SNAPSHOTS]
                is_new = True
            self._snap_dir.mkdir(parents=True, exist_ok=True)
            self._write(self._snap_path(conn_id), {"versions": versions})
            return is_new, previous

    def has_snapshots(self, conn_id: str) -> bool:
        return bool(self._load_versions(conn_id))

    def list_snapshots(self, conn_id: str) -> list:
        """Versiones, la más nueva primero (sin el contenido)."""
        with self._lock:
            out = []
            for i, v in enumerate(self._load_versions(conn_id)):
                t = v.get("tables", {})
                out.append({
                    "index": i, "at": v.get("at"), "last_seen": v.get("last_seen"),
                    "tables": len(t), "columns": sum(len(x["c"]) for x in t.values()),
                    "relations": sum(len(x["r"]) for x in t.values()),
                })
            return out

    def get_snapshot(self, conn_id: str, index: int):
        with self._lock:
            versions = self._load_versions(conn_id)
            return versions[index] if 0 <= index < len(versions) else None

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
