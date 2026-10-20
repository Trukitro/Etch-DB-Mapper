# Arquitectura — Etch-DB-Mapper 2.x

Aplicación de escritorio en dos capas que se hablan por un puente de pywebview:

```
┌──────────────────────────── ventana pywebview (Edge WebView2 / WebKitGTK) ───────────────┐
│ webui/  HTML + CSS + JS (sin build)                                                       │
│   app.js ── estado, rutas, escaneo, atajos        views/*.js ── home, overview, explorer, │
│   sidebar.js, dialogs.js, toast.js, util.js                    map (Cytoscape), docs     │
└───────────────▲──────────────────────────────────────────────────┬───────────────────────┘
                │ evaluate_js("EtchBridge.emit(evento, datos)")    │ window.pywebview.api.metodo(...)
┌───────────────┴──────────────────────────────────────────────────▼───────────────────────┐
│ core/api.py  (clase Api: métodos públicos = lo que ve JS)                                 │
│   ├─ core/storage.py   Store: db_maps.json + settings.json (atómico, con id estable)      │
│   ├─ core/scanner.py   run_db_scan(uri, progress) → esquema + meta  (pyDAL)               │
│   └─ core/demo.py, core/paths.py, core/version.py                                         │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

No hay servidor HTTP ni Flask: la interfaz se carga desde `file://` y habla con Python solo por el puente. Todo corre en un proceso.

## Decisiones clave

- **Sin módulos ES.** Chromium bloquea `<script type="module">` en `file://`, así que los scripts son clásicos y cuelgan de `window.Etch`. Orden de carga en `webui/index.html`.
- **Nada de `innerHTML` con datos de la base.** Los nombres de tablas/columnas pueden contener cualquier cosa; la UI construye el DOM con `h()` (`util.js`). La única excepción es el Markdown de `HELP.md`/`CHANGELOG.md`, que es contenido propio y se escapa antes (`renderMarkdown`).
- **CSP estricta** en `index.html` (`default-src 'none'`, scripts solo locales). `connect-src 'self'` existe solo para el modo desarrollo.
- **Solo lectura de metadatos.** El scanner no ejecuta nada contra las tablas del usuario, únicamente consultas al catálogo del motor.
- **Las URI no se exponen completas.** Las listas y eventos llevan `masked_uri`; la URI real solo viaja en `get_connection` (para editar) y vive en el archivo local del usuario.
- **Las tareas largas corren en un hilo** y avisan por eventos; la UI nunca espera una consulta.

## API Python → JS

Cada método público de `Api` es invocable desde JS (`Etch.api.metodo(...)` devuelve una promesa con un `dict`). Los métodos con `_` son internos y pywebview no los expone. Los errores esperables vuelven como `{"ok": false, "error": "..."}`.

| Método | Qué hace |
|---|---|
| `bootstrap()` | Versión, ajustes, lista de conexiones, avisos de carga |
| `save_settings(patch)` | Guarda ajustes conocidos (tema, barra lateral, layout del mapa…) |
| `get_help()`, `get_changelog()` | Markdown empaquetado |
| `open_external(url)` | Abre solo `http(s)` en el navegador del sistema |
| `list_connections()`, `get_connection(alias)` | Resúmenes / URI completa para editar |
| `check_uri(uri)` | Motor detectado y driver instalado (sin conectar) |
| `save_connection(alias, uri, previous_alias)` | Crea/edita/renombra **antes** de escanear |
| `rename_connection(old, new)`, `delete_connection(alias)` | Gestión |
| `create_demo_connection()` | Crea la base SQLite de ejemplo |
| `start_scan(alias)` | Lanza el escaneo en un hilo |
| `get_schema(alias)` | Esquema normalizado + meta + posiciones del mapa |
| `save_map_state(alias, state)` | Posiciones (saneadas) y layout |
| `pick_file()`, `save_file(nombre, contenido, encoding)` | Diálogos nativos |

### Eventos Python → JS

`scan_started`, `scan_progress` (`phase`: connect · tables · columns · keys · relations · build, `message`, `pct`), `scan_finished` (`ok`, `message`, `connection`). Se emiten con `window.evaluate_js("EtchBridge.emit(...)")`; en la UI se escuchan con `Etch.on(evento, fn)`.

## Formato del esquema

`run_db_scan()` devuelve `{"status": "success", "data": tablas, "meta": {...}, "last_scan", "duration_sec"}` o `{"status": "error", "message"}`. Cada tabla:

```json
{
  "schema": "dbo",
  "name": "Orders",
  "columns": [{"name": "OrderID", "type": "int", "null": false, "pk": true, "fk": false}],
  "relations": [{"col": "CustomerID", "ref_table": "Customers", "ref_col": "CustomerID"}]
}
```

- La clave del diccionario es el nombre de la tabla; si el mismo nombre existe en varios esquemas, se usa `esquema.nombre`.
- `get_schema` agrega `referenced_by` (relaciones entrantes) mediante `finalize_schema`, que además acepta el formato 1.x (`null: "YES"`, `is_pk`).
- `meta`: `table_count`, `column_count`, `relation_count`, `related_count`, `orphan_count`, `no_pk_count`.

## Agregar un lector de esquema para otro motor

`scanner.INTROSPECTORS` asocia el nombre del motor con una función `introspect(db, engine, emit)` que devuelve el esquema en bruto y llama a `emit(fase, mensaje, pct)` para informar el progreso. El formato en bruto es un diccionario con cuatro listas de tuplas:

```python
{
  "tables":  [(schema, table)],
  "columns": [(schema, table, column, type, nullable)],            # en orden
  "pks":     [(schema, table, column)],
  "fks":     [(schema, table, column, ref_schema, ref_table, ref_column)],
}
```

1. Escribí `_introspect_<motor>(db, engine, emit)` en `core/scanner.py`. Tiene que hacer **un número fijo de consultas** (no una por tabla) y no interpolar texto del usuario en el SQL.
2. Registralo en `INTROSPECTORS["<motor>"]`. El nombre del motor lo da `detect_engine(uri)` a partir del prefijo de la URI.
3. Si el motor necesita un driver Python, agregalo en `DRIVER_HINTS` para dar un mensaje claro cuando falte.
4. Si el motor expone un `INFORMATION_SCHEMA` estándar, probablemente no necesites nada: se usa `_introspect_information_schema` para los motores no registrados.
5. Agregá una prueba en `tests/test_scanner.py`. Para motores sin servidor local, probá la lógica de construcción con filas simuladas.

## Almacenamiento

Carpeta de datos (`ETCH_DATA_DIR` o `--data-dir` la reemplazan):

| SO | Ruta |
|---|---|
| Windows | `%LOCALAPPDATA%\Etch-DB-Mapper` |
| Linux | `$XDG_DATA_HOME/Etch-DB-Mapper` (por defecto `~/.local/share/Etch-DB-Mapper`) |
| macOS | `~/Library/Application Support/Etch-DB-Mapper` |

Archivos: `db_maps.json` (compatible con 1.x), `settings.json`, `etch.log`, `webview/` (perfil del motor web). Las escrituras son atómicas (archivo temporal + `os.replace`) y, si un JSON está corrupto, se guarda como `*.corrupt-<fecha>` y se avisa en la UI.

Cada conexión tiene un `id` estable: permite renombrar sin perder el estado y descartar resultados de escaneos viejos (si se reintenta o se borra la conexión mientras uno corre, el resultado tardío se ignora).

## Mapa

`webui/js/views/map.js` usa Cytoscape.js + `fcose`. Las posiciones se guardan por conexión en `map.positions` (clave distinta de la `positions` de 1.x). Al abrir el mapa solo se calcula layout para las tablas sin posición guardada (las demás quedan fijas); «Auto-organizar» descarta las guardadas. Las tablas huérfanas del alcance «todas» se ubican en una grilla debajo del resto. En alcance «vecindad» las posiciones no se guardan.

## Modo desarrollo en el navegador

Sin pywebview (`window.pywebview` ausente) `bridge.js` carga `webui/js/dev/mock-api.js`, una API simulada con datos ficticios (incluida una base de 171 tablas). Sirve para iterar la UI sin ventana nativa:

```bash
python -m http.server 8765
# abrir http://localhost:8765/webui/index.html
```

## Empaquetado

`tools/build_windows.ps1` compila sintaxis y pruebas, genera el `.exe` con PyInstaller (`--onefile --windowed`, `--add-data` para `webui/`, `HELP.md`, `CHANGELOG.md`) y, con `-Installer`, el instalador con Inno Setup (`installer/setup.iss`, versión tomada de `core/version.py`). Los recursos se leen con `core.paths.resource_path`, que funciona igual en desarrollo y empaquetado.
