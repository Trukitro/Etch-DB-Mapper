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
│   ├─ core/uri.py       Construir/descomponer URI del asistente de conexión
│   ├─ core/secrets.py   Cifrado de contraseñas (DPAPI en Windows)
│   ├─ core/storage.py   Store: db_maps.json + settings.json + snapshots/ (atómico, id estable)
│   ├─ core/inference.py Relaciones probables por nombre · core/diff.py Comparación de versiones
│   ├─ core/joins.py     Caminos entre tablas + SQL de JOIN · core/docs_export.py Diccionario: MD/CSV/HTML
│   ├─ core/updates.py   Aviso de versión nueva (opcional) · core/logs.py Registro sin contraseñas      │
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
- **Credenciales codificadas.** El asistente codifica usuario y clave con porcentaje y `_open_dal` abre pydal con `decode_credentials=True`; así `@ : / %` no rompen la URI.
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
| `list_drivers()` | Drivers ODBC de SQL Server instalados y drivers de Python faltantes por motor |
| `build_uri(campos)`, `parse_uri(uri)` | Asistente de conexión: arma la URI (con codificación de usuario y clave) y la descompone |
| `test_connection(uri)` | Driver + alcance de red + `SELECT 1`; no guarda ni lee el esquema |
| `save_connection(alias, uri, previous_alias)` | Crea/edita/renombra **antes** de escanear |
| `rename_connection(old, new)`, `delete_connection(alias)` | Gestión |
| `create_demo_connection()` | Crea la base SQLite de ejemplo |
| `start_scan(alias)` | Lanza el escaneo en un hilo |
| `get_schema(alias)` | Esquema normalizado + meta + `inferred` (relaciones probables) + nº de versiones + posiciones del mapa |
| `list_versions(alias)`, `compare_versions(alias, newer, older)` | Historial de versiones del esquema y su diferencia |
| `save_annotation(alias, tabla, columna, campos)` | Nota/etiquetas/responsable de una tabla o nota de una columna (se guarda en `annotations/`) |
| `find_paths(alias, origen, destino, incluir_probables)` | Caminos entre dos tablas + SQL del JOIN |
| `export_docs(alias, formato)` | Diccionario de datos: `markdown`, `csv` o `html` (informe con mapa) |
| `security_status()` | Estado del cifrado de contraseñas |
| `check_updates(force)` | Consulta (opcional) la última versión en GitHub |
| `open_data_folder()` | Abre la carpeta de datos en el explorador del sistema |
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

## Seguridad de las contraseñas

`Store` cifra la URI completa de toda conexión que tenga contraseña (`uri_enc`, con el protector de `core/secrets.py`) y deja en `uri` solo la versión oculta (`usuario:••••@host`). `Store.get()` devuelve una **copia** con la URI descifrada en memoria, así que el resto del código no cambia; si el descifrado falla (otro usuario/equipo) la copia lleva `secret_error: true` y la UI pide volver a escribirla. Las URI antiguas en claro se migran al cargar. Sin protector disponible (Linux/macOS por ahora) no se simula cifrado: `security_status()` lo informa. Detalle y modelo de amenazas: [`../SECURITY.md`](../SECURITY.md).

## Historial de versiones y comparación

Cada escaneo exitoso llama a `Store.add_snapshot()`: guarda el esquema en forma compacta (`compact_schema`) en `snapshots/<id>.json` (últimas 8 versiones, deduplicadas por hash; si el esquema no cambió solo se actualiza `last_seen`). `core/diff.py` compara dos versiones (tablas añadidas/quitadas, columnas añadidas/quitadas/modificadas, relaciones) y `scan_finished` incluye `changes` con el resumen respecto de la versión anterior. Las conexiones previas a 2.2 usan su esquema guardado como versión base.

## Documentación, rutas y exportación

- **Descripciones nativas.** `scanner._comments()` hace una consulta de solo lectura por motor (PostgreSQL `pg_description`, SQL Server `sys.extended_properties` con `MS_Description`, MySQL `*_COMMENT`) y el resultado llega a `table.comment` / `column.comment`. Si falla (permisos, motor sin soporte) devuelve `[]` y el escaneo sigue. Verificada la sintaxis de PostgreSQL contra un servidor real; la de SQL Server y MySQL está revisada pero **sin probar contra servidores reales**.
- **Notas del usuario.** `Store.set_annotation()` guarda en `annotations/<id>.json` (clave = nombre de tabla/columna, con límites de tamaño). `get_schema` las devuelve en `annotations`. La descripción efectiva es *nota del usuario > comentario de la base*.
- **Rutas.** `core/joins.py` arma el grafo con las FK (y las relaciones probables si se pide), busca los caminos simples más cortos (con un presupuesto de expansiones para grafos densos) y los ordena: primero los que solo usan claves reales. `join_sql()` cita los identificadores según el motor y califica con el esquema.
- **Exportación.** `core/docs_export.py` genera Markdown, CSV (con BOM para Excel) e informe HTML. El informe incrusta Cytoscape (de `webui/vendor/`), los datos como JSON inerte (`</` escapado) y escapa con `html.escape` todo texto de la base o del usuario; no usa recursos remotos.

## Relaciones probables

`core/inference.py::infer_relations(tables)` trabaja sobre el esquema ya leído (sin tocar la base). Reglas: misma columna que una PK única y no genérica → *alta*; nombre de columna sin sufijo (`ID`, `Key`, `Cod`…) que coincide con una tabla (con/sin prefijo, singular/plural) → *media*; tipos compatibles obligatorios; ante varias tablas candidatas se prefiere el mismo prefijo y, si hay empate, se omite. La UI las agrega a `relations` con `inferred: true` y las dibuja punteadas.

## Almacenamiento

Carpeta de datos (`ETCH_DATA_DIR` o `--data-dir` la reemplazan):

| SO | Ruta |
|---|---|
| Windows | `%LOCALAPPDATA%\Etch-DB-Mapper` |
| Linux | `$XDG_DATA_HOME/Etch-DB-Mapper` (por defecto `~/.local/share/Etch-DB-Mapper`) |
| macOS | `~/Library/Application Support/Etch-DB-Mapper` |

Archivos: `db_maps.json` (compatible con 1.x; las contraseñas van cifradas), `settings.json`, `snapshots/` (historial de versiones), `etch.log`. Las escrituras son atómicas (archivo temporal + `os.replace`) y, si un JSON está corrupto, se guarda como `*.corrupt-<fecha>` y se avisa en la UI.

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
