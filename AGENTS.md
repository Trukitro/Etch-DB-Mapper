# AGENTS.md

## Proyecto
Etch-DB-Mapper es una app de escritorio para mapear esquemas de bases de datos
relacionales a través de `pydal` (cualquier motor que pydal pueda abrir;
probado con SQL Server, PostgreSQL y SQLite).
Usa:
- pywebview (ventana nativa) + HTML/CSS/JS vanilla para la UI (`webui/`)
- Cytoscape.js + fcose (vendorizados) para el mapa
- pydal para la conexión a la base de datos
- JSON local para conexiones y ajustes

## Estructura
- `db_manager_app.py`: launcher (crea la ventana y expone la API).
- `core/api.py`: API que ve la UI (`window.pywebview.api.*`) y eventos de escaneo.
- `core/scanner.py`: lectores de esquema por motor (`INTROSPECTORS`).
- `core/storage.py`: lectura/escritura JSON atómica.
- `core/paths.py`, `core/demo.py`, `core/version.py`.
- `webui/`: interfaz (`index.html`, `css/`, `js/`, `vendor/`, `assets/`).
- `tests/`: pruebas `unittest`. `tools/build_windows.ps1`: build completo.
- `docs/ARCHITECTURE.md`: leerlo antes de tocar el puente Python↔JS.

## Reglas
- Lógica de base de datos en `core/`; la UI solo presenta. No mover lógica
  pesada a `db_manager_app.py`.
- Los métodos públicos de `Api` son lo que JS puede llamar: los internos
  empiezan con `_`. Devolver `dict` JSON-serializable y errores esperables como
  `{"ok": False, "error": "..."}`.
- Tareas largas en un hilo; avisar a la UI con eventos (`_emit`), nunca bloquear.
- En JS: sin módulos ES (la app se sirve desde `file://`), todo en `window.Etch`;
  construir DOM con `h()` y **nunca** `innerHTML` con datos de la base.
- No hardcodear credenciales ni URIs. No agregar dependencias salvo que sean necesarias.
- Antes de cambiar `scanner.py`: nada de concatenar texto externo en el SQL; un
  número fijo de consultas (no una por tabla); probar con SQLite (`tests/`).
- Validar cambios con:
  `python -m unittest discover -s tests -t .` y
  `python -m py_compile db_manager_app.py core/api.py core/scanner.py core/storage.py core/paths.py core/demo.py`.
- La UI se itera sin ventana nativa: `python -m http.server 8765` y abrir
  `http://localhost:8765/webui/index.html` (usa `webui/js/dev/mock-api.js`).
- Documentar cambios importantes en `README.md`, `CHANGELOG.md` y `docs/`.
- Este es el repo público. No incluir datos, credenciales ni referencias de
  ningún cliente o entorno de trabajo real — solo datos de prueba genéricos.
- El autor prueba manualmente contra una base Postgres local propia y,
  puntualmente, contra un SQL Server real de su trabajo (para diagnosticar
  bugs específicos de motor) — ninguna de las dos URIs vive en este repo ni
  se versiona nunca. Si el autor comparte una URI real en el chat para
  diagnóstico, usarla solo en memoria (nunca escribirla a un archivo del
  proyecto, ni a `db_maps.json`/la carpeta de datos, ni a un commit) y no
  pedirla ni asumirla en el código — el scanner debe seguir funcionando por
  URI arbitraria que el usuario ingrese.

## Estilo
- Código claro, simple y compatible con Windows (y con Linux en lo posible).
- Mensajes de UI en español.
- Commits: Conventional Commits, identidad `Rikion <rickninetail@hotmail.com>`.
