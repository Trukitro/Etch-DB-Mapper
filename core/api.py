"""API que pywebview expone a la UI (window.pywebview.api.<método>).

Convenciones
------------
* Todo lo que empieza con "_" es interno y pywebview NO lo expone a JS
  (importante: así no se serializa la ventana, el store ni los locks).
* Cada método público devuelve un dict JSON-serializable; los errores
  "esperables" vuelven como {"ok": False, "error": "..."} para que la UI
  los muestre como notificación, sin excepciones cruzando el puente.
* El escaneo corre en un hilo y avisa a la UI con eventos
  (scan_started / scan_progress / scan_finished) vía evaluate_js.
"""
import base64
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime

from . import updates
from . import uri as uri_tools
from .demo import DEMO_ALIAS, create_demo_db
from . import docs_export, joins
from .diff import describe, diff_schemas
from .inference import infer_relations
from .paths import resource_path
from .storage import compact_schema
from .scanner import (
    check_driver_available, compute_meta, detect_engine, finalize_schema, inspect_uri, mask_uri, run_db_scan,
    summarize_error, test_connection,
)
from .version import APP_NAME, REPO_URL, __version__

log = logging.getLogger("etch.api")
MAX_ALIAS_LEN = 60


class Api:
    def __init__(self, store, window=None):
        self._store = store
        self._window = window
        self._lock = threading.Lock()
        self._counter = 0
        self._scans: dict = {}   # conn_id -> estado del escaneo en curso

    def _bind(self, window):
        self._window = window

    # ------------------------------------------------------------- internos
    def _emit(self, event: str, payload: dict):
        window = self._window
        if window is None:
            return
        try:
            window.evaluate_js(
                "window.EtchBridge && window.EtchBridge.emit(%s, %s)" % (json.dumps(event), json.dumps(payload))
            )
        except Exception:  # la ventana pudo cerrarse mientras escaneaba
            log.debug("No se pudo emitir '%s' a la UI", event, exc_info=True)

    @staticmethod
    def _status(entry: dict) -> str:
        # Compatibilidad con historiales 1.x sin campo 'status'.
        return entry.get("status") or ("success" if entry.get("data") else "pending")

    def _summary(self, alias: str, entry: dict) -> dict:
        meta = entry.get("meta")
        if not meta and entry.get("data"):   # historiales 1.x sin 'meta': se calcula una vez y se guarda
            meta = compute_meta(finalize_schema(entry["data"]))
            self._store.update(alias, meta=meta)
        meta = meta or {}
        with self._lock:
            scan = dict(self._scans.get(entry["id"], {})) or None
        uri = entry.get("uri", "")
        return {
            "id": entry["id"],
            "alias": alias,
            "engine": detect_engine(uri),
            "masked_uri": mask_uri(uri),
            "status": self._status(entry),
            "last_scan": entry.get("last_scan"),
            "duration_sec": entry.get("duration_sec", 0),
            "last_error": entry.get("last_error"),
            "table_count": meta.get("table_count", 0),
            "relation_count": meta.get("relation_count", 0),
            "has_data": bool(entry.get("data")),
            "secret_error": bool(entry.get("secret_error")),
            "scan": scan,
        }

    @staticmethod
    def _check_alias(alias: str):
        if not alias:
            return "Poné un nombre para la conexión."
        if len(alias) > MAX_ALIAS_LEN:
            return f"El nombre es demasiado largo (máximo {MAX_ALIAS_LEN} caracteres)."
        return None

    # ---------------------------------------------------------------- app
    def bootstrap(self) -> dict:
        return {
            "app_name": APP_NAME,
            "version": __version__,
            "repo_url": REPO_URL,
            "platform": sys.platform,
            "data_dir": str(self._store.dir),
            "settings": self._store.settings(),
            "security": self._store.security_status(),
            "update_check_blocked": updates.disabled_by_env(),
            "connections": self.list_connections(),
            "warnings": list(self._store.load_warnings),
        }

    def save_settings(self, patch: dict) -> dict:
        return {"ok": True, "settings": self._store.patch_settings(patch or {})}

    def get_changelog(self) -> dict:
        return self._read_doc("CHANGELOG.md", "# Changelog\n\nNo se encontró CHANGELOG.md en este paquete.")

    def get_help(self) -> dict:
        return self._read_doc("HELP.md", "# Ayuda\n\nNo se encontró HELP.md en este paquete.")

    @staticmethod
    def _read_doc(name: str, fallback: str) -> dict:
        try:
            return {"ok": True, "markdown": resource_path(name).read_text(encoding="utf-8")}
        except OSError:
            return {"ok": True, "markdown": fallback}

    def open_external(self, url: str) -> dict:
        if not isinstance(url, str) or not url.lower().startswith(("https://", "http://")):
            return {"ok": False, "error": "Solo se pueden abrir enlaces http(s)."}
        webbrowser.open(url)
        return {"ok": True}

    def log_js(self, level: str, message: str) -> dict:
        """Errores del frontend al etch.log (la app empaquetada no tiene consola)."""
        getattr(log, level if level in ("debug", "info", "warning", "error") else "error")("[js] %s", str(message)[:2000])
        return {"ok": True}

    # ---------------------------------------------------------- conexiones
    def list_connections(self) -> list:
        return [self._summary(a, self._store.get(a)) for a in self._store.aliases()]

    def check_uri(self, uri: str) -> dict:
        return inspect_uri((uri or "").strip())

    def list_drivers(self) -> dict:
        """Para el asistente: drivers ODBC de SQL Server instalados y qué motores
        no tienen su driver de Python."""
        missing = {e: check_driver_available(info["scheme"] + "://") for e, info in uri_tools.ENGINES.items()}
        return {
            "odbc": uri_tools.odbc_drivers(),
            "engines": {e: {"label": info["label"], "port": info["port"], "driver_error": missing[e]}
                        for e, info in uri_tools.ENGINES.items()},
        }

    def build_uri(self, fields: dict) -> dict:
        try:
            uri = uri_tools.build_uri(fields or {})
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "uri": uri, "masked": mask_uri(uri)}

    def parse_uri(self, uri: str) -> dict:
        fields = uri_tools.parse_uri(uri)
        return {"ok": fields is not None, "fields": fields}

    def test_connection(self, uri: str) -> dict:
        """Conecta y hace un SELECT 1 (no lee el esquema ni guarda nada)."""
        return test_connection((uri or "").strip())

    def get_connection(self, alias: str) -> dict:
        entry = self._store.get(alias)
        if not entry:
            return {"ok": False, "error": "La conexión ya no existe."}
        return {"ok": True, "alias": alias, "uri": entry.get("uri", ""), "secret_error": bool(entry.get("secret_error"))}

    def save_connection(self, alias: str, uri: str, previous_alias: str = None) -> dict:
        """Crea o edita una conexión y la guarda YA (antes de escanear), así
        una URI que falla nunca se pierde. Si `previous_alias` es distinto
        de `alias`, además renombra."""
        alias, uri = (alias or "").strip(), (uri or "").strip()
        error = self._check_alias(alias)
        if error:
            return {"ok": False, "error": error}
        if "://" not in uri:
            return {"ok": False, "error": "La URI debe tener la forma motor://usuario:clave@host:puerto/base"}

        store = self._store
        if previous_alias and store.exists(previous_alias):
            if alias != previous_alias:
                if store.exists(alias):
                    return {"ok": False, "error": f"Ya existe una conexión llamada '{alias}'."}
                store.rename(previous_alias, alias)
        elif store.exists(alias):
            return {"ok": False, "error": f"Ya existe una conexión llamada '{alias}'. Editala desde la barra lateral."}

        entry = store.get(alias)
        if entry is None:
            store.put(alias, {
                "uri": uri, "status": "pending", "data": {}, "meta": {}, "map": {},
                "last_scan": None, "duration_sec": 0, "last_error": None,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })
        elif uri != entry.get("uri"):
            store.update(alias, uri=uri, status="pending", last_error=None)
        return {"ok": True, "alias": alias, "connection": self._summary(alias, store.get(alias))}

    def rename_connection(self, old: str, new: str) -> dict:
        new = (new or "").strip()
        error = self._check_alias(new)
        if error:
            return {"ok": False, "error": error}
        if not self._store.exists(old):
            return {"ok": False, "error": "La conexión ya no existe."}
        try:
            self._store.rename(old, new)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "alias": new, "connections": self.list_connections()}

    def delete_connection(self, alias: str) -> dict:
        entry = self._store.get(alias)
        if entry:
            with self._lock:
                self._scans.pop(entry["id"], None)   # un escaneo en vuelo queda "viejo" y se descarta
            self._store.delete(alias)
        return {"ok": True, "connections": self.list_connections()}

    def create_demo_connection(self) -> dict:
        uri = create_demo_db(self._store.dir / "demo" / "tienda.sqlite")
        if self._store.exists(DEMO_ALIAS):
            self._store.update(DEMO_ALIAS, uri=uri)
        else:
            self._store.put(DEMO_ALIAS, {
                "uri": uri, "status": "pending", "data": {}, "meta": {}, "map": {},
                "last_scan": None, "duration_sec": 0, "last_error": None,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })
        return {"ok": True, "alias": DEMO_ALIAS, "connection": self._summary(DEMO_ALIAS, self._store.get(DEMO_ALIAS))}

    # ------------------------------------------------------------- escaneo
    def start_scan(self, alias: str) -> dict:
        entry = self._store.get(alias)
        if not entry:
            return {"ok": False, "error": "La conexión ya no existe."}
        if entry.get("secret_error"):
            return {"ok": False, "error": "No se pudo descifrar la contraseña guardada (¿otro usuario de Windows o "
                                           "otro equipo?). Editá la conexión y volvé a escribirla."}
        conn_id = entry["id"]
        with self._lock:
            self._counter += 1
            generation = self._counter
            self._scans[conn_id] = {
                "gen": generation, "running": True, "phase": "connect",
                "message": "Conectando…", "pct": 0, "started": time.time(),
            }
        self._store.update(alias, status="pending", last_error=None)
        self._emit("scan_started", {"alias": alias, "id": conn_id})
        threading.Thread(target=self._scan_worker, args=(conn_id, generation, entry["uri"]), daemon=True).start()
        return {"ok": True}

    def _is_stale(self, conn_id: str, generation: int) -> bool:
        # Si se reintentó (o se borró la conexión) mientras este hilo
        # corría, su resultado llega tarde y NO debe pisar al más nuevo.
        with self._lock:
            scan = self._scans.get(conn_id)
            return scan is None or scan["gen"] != generation

    def _scan_worker(self, conn_id: str, generation: int, uri: str):
        def progress(phase, message, pct):
            if self._is_stale(conn_id, generation):
                return
            with self._lock:
                scan = self._scans.get(conn_id)
                if scan:
                    scan.update(phase=phase, message=message, pct=pct)
            alias = self._store.alias_by_id(conn_id)
            if alias:
                self._emit("scan_progress", {"alias": alias, "id": conn_id, "phase": phase, "message": message, "pct": pct})

        try:
            result = run_db_scan(uri, progress)
        except Exception as e:   # run_db_scan no debería lanzar, pero un hilo no puede morir en silencio
            log.exception("Escaneo falló de forma inesperada")
            result = {"status": "error", "message": summarize_error(e)}

        if self._is_stale(conn_id, generation):
            return
        alias = self._store.alias_by_id(conn_id)
        with self._lock:
            self._scans.pop(conn_id, None)
        if alias is None:
            return
        changes = None
        if result["status"] == "success":
            changes = self._record_version(alias, conn_id, result)
            self._store.update(
                alias, status="success", data=result["data"], meta=result["meta"],
                last_scan=result["last_scan"], duration_sec=result["duration_sec"], last_error=None,
            )
        else:
            self._store.update(alias, status="error", last_error=result["message"])
        self._emit("scan_finished", {
            "alias": alias, "id": conn_id, "ok": result["status"] == "success", "changes": changes,
            "message": result.get("message"), "connection": self._summary(alias, self._store.get(alias)),
        })

    def _record_version(self, alias: str, conn_id: str, result: dict):
        """Guarda el esquema como una versión del historial y devuelve el resumen de
        cambios respecto de la versión anterior (None si es el primer escaneo).
        Un fallo acá nunca debe tirar abajo el escaneo."""
        try:
            old = self._store.get(alias)
            if not self._store.has_snapshots(conn_id) and old.get("data"):
                # conexión anterior a 2.2: su esquema guardado pasa a ser la versión base
                self._store.add_snapshot(conn_id, finalize_schema(old["data"]), old.get("last_scan") or "")
            had_history = self._store.has_snapshots(conn_id)
            is_new, previous = self._store.add_snapshot(conn_id, result["data"], result["last_scan"])
            if not had_history:
                return None
            if not is_new:
                return {"total": 0, "text": "sin cambios"}
            summary = diff_schemas(previous["tables"], compact_schema(result["data"]))["summary"]
            return {**summary, "text": describe(summary)}
        except Exception:
            log.exception("No se pudo registrar la versión del esquema")
            return None

    # --------------------------------------------------------------- datos
    def get_schema(self, alias: str) -> dict:
        entry = self._store.get(alias)
        if not entry:
            return {"ok": False, "error": "La conexión ya no existe."}
        tables = finalize_schema(entry.get("data") or {})
        meta = compute_meta(tables)
        inferred = infer_relations(tables)
        meta["inferred_count"] = len(inferred)
        return {
            "ok": True,
            "alias": alias,
            "engine": detect_engine(entry.get("uri")),
            "status": self._status(entry),
            "last_scan": entry.get("last_scan"),
            "duration_sec": entry.get("duration_sec", 0),
            "last_error": entry.get("last_error"),
            "tables": tables,
            "meta": meta,
            "inferred": inferred,
            "versions": len(self._store.list_snapshots(entry["id"])),
            "annotations": self._store.get_annotations(entry["id"]),
            "map": entry.get("map") or {},
        }

    # ------------------------------------------------ documentación (2.3)
    def save_annotation(self, alias: str, table: str, column=None, fields=None) -> dict:
        """Notas/etiquetas/responsable de una tabla (column=None) o nota de una columna."""
        entry = self._store.get(alias)
        if not entry:
            return {"ok": False, "error": "La conexión ya no existe."}
        try:
            saved = self._store.set_annotation(entry["id"], table, column, fields or {})
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "annotation": saved}

    def _schema_for(self, alias: str):
        entry = self._store.get(alias)
        if not entry or not entry.get("data"):
            return None, None
        tables = finalize_schema(entry["data"])
        return entry, tables

    def find_paths(self, alias: str, source: str, target: str, include_inferred: bool = True) -> dict:
        """Caminos entre dos tablas por claves foráneas (y relaciones probables) + SQL del JOIN."""
        entry, tables = self._schema_for(alias)
        if tables is None:
            return {"ok": False, "error": "Escanea la conexión primero."}
        if source not in tables or target not in tables:
            return {"ok": False, "error": "Elige dos tablas del esquema."}
        if source == target:
            return {"ok": False, "error": "Elige dos tablas distintas."}
        engine = detect_engine(entry.get("uri"))
        found = joins.find_paths(tables, infer_relations(tables), source, target, bool(include_inferred))
        return {"ok": True, "paths": [
            {"steps": p, "length": len(p), "inferred": sum(1 for st in p if st["inferred"]), "sql": joins.join_sql(engine, tables, p)}
            for p in found]}

    def export_docs(self, alias: str, kind: str) -> dict:
        """Genera el diccionario de datos: 'markdown', 'csv' o 'html' (informe interactivo)."""
        entry, tables = self._schema_for(alias)
        if tables is None:
            return {"ok": False, "error": "Escanea la conexión primero."}
        inferred = infer_relations(tables)
        cards = docs_export.collect(tables, inferred, self._store.get_annotations(entry["id"]))
        engine = detect_engine(entry.get("uri"))
        base = "diccionario_" + alias
        try:
            if kind == "markdown":
                return {"ok": True, "filename": docs_export.safe_filename(base, "md"),
                        "content": docs_export.export_markdown(alias, engine, cards, entry.get("last_scan"))}
            if kind == "csv":
                return {"ok": True, "filename": docs_export.safe_filename(base, "csv"), "content": docs_export.export_csv(cards)}
            if kind == "html":
                return {"ok": True, "filename": docs_export.safe_filename("informe_" + alias, "html"),
                        "content": docs_export.export_html(alias, engine, cards, inferred, entry.get("last_scan"),
                                                           (entry.get("map") or {}).get("positions"))}
        except OSError as e:   # p. ej. falta algún archivo del paquete
            return {"ok": False, "error": f"No se pudo generar el informe: {e}"}
        return {"ok": False, "error": "Formato desconocido."}

    # ----------------------------------------------- historial y comparación
    def list_versions(self, alias: str) -> dict:
        entry = self._store.get(alias)
        if not entry:
            return {"ok": False, "error": "La conexión ya no existe."}
        return {"ok": True, "versions": self._store.list_snapshots(entry["id"])}

    def compare_versions(self, alias: str, newer: int = 0, older: int = 1) -> dict:
        """Compara dos versiones del historial (0 = la más nueva)."""
        entry = self._store.get(alias)
        if not entry:
            return {"ok": False, "error": "La conexión ya no existe."}
        a, b = self._store.get_snapshot(entry["id"], int(older)), self._store.get_snapshot(entry["id"], int(newer))
        if a is None or b is None:
            return {"ok": False, "error": "Todavía no hay dos versiones para comparar."}
        return {"ok": True, "older": {"index": int(older), "at": a["at"]}, "newer": {"index": int(newer), "at": b["at"]},
                "diff": diff_schemas(a["tables"], b["tables"])}

    # ------------------------------------------------- seguridad y versiones
    def security_status(self) -> dict:
        return self._store.security_status()

    def check_updates(self, force: bool = False) -> dict:
        """Busca una versión nueva en GitHub (ver core/updates.py). Sin `force` respeta el
        ajuste del usuario y consulta como máximo una vez al día."""
        settings = self._store.settings()
        if updates.disabled_by_env():
            return {"ok": False, "skipped": True, "error": "Desactivado por la variable ETCH_NO_UPDATE_CHECK."}
        if not force:
            if not settings.get("check_updates"):
                return {"ok": False, "skipped": True, "error": "Búsqueda automática desactivada."}
            last = settings.get("last_update_check") or ""
            try:
                if last and (datetime.now() - datetime.fromisoformat(last)).total_seconds() < 24 * 3600:
                    return {"ok": False, "skipped": True, "error": "Ya se consultó hoy."}
            except ValueError:
                pass
        result = updates.check_latest()
        if result["ok"]:
            self._store.patch_settings({"last_update_check": datetime.now().isoformat(timespec="seconds")})
        return result

    def open_data_folder(self) -> dict:
        folder = str(self._store.dir)
        try:
            if sys.platform == "win32":
                os.startfile(folder)   # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": folder}

    def save_map_state(self, alias: str, state: dict) -> dict:
        if not self._store.exists(alias) or not isinstance(state, dict):
            return {"ok": False}
        positions = {}
        for name, pos in list((state.get("positions") or {}).items())[:20000]:
            try:
                x, y = float(pos["x"]), float(pos["y"])
            except (KeyError, TypeError, ValueError):
                continue
            if abs(x) < 1e7 and abs(y) < 1e7:
                positions[str(name)] = {"x": round(x, 1), "y": round(y, 1)}
        self._store.update(alias, map={"positions": positions, "layout": str(state.get("layout") or "fcose")})
        return {"ok": True}

    # ------------------------------------------------------------ archivos
    def pick_file(self) -> dict:
        """Diálogo nativo para elegir un archivo SQLite."""
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        picked = self._window.create_file_dialog(
            kind, file_types=("Bases SQLite (*.db;*.sqlite;*.sqlite3)", "Todos los archivos (*.*)")
        ) if self._window else None
        return {"ok": bool(picked), "path": (picked[0] if picked else None)}

    def save_file(self, suggested_name: str, content: str, encoding: str = "text") -> dict:
        """Diálogo 'Guardar como' y escritura (para exportar PNG/SQL/JSON)."""
        import webview
        if not self._window:
            return {"ok": False, "error": "Sin ventana."}
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        picked = self._window.create_file_dialog(kind, save_filename=suggested_name)
        if not picked:
            return {"ok": False, "cancelled": True}
        path = picked if isinstance(picked, str) else picked[0]
        try:
            if encoding == "base64":
                with open(path, "wb") as f:
                    f.write(base64.b64decode(content))
            else:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
        except OSError as e:
            return {"ok": False, "error": f"No se pudo guardar: {e}"}
        return {"ok": True, "path": path}
