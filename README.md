# Etch-DB-Mapper

**Etch-DB-Mapper** lee el esquema de una base de datos —tablas, columnas, claves y relaciones— y te lo muestra como un explorador buscable y un mapa interactivo. Funciona con cualquier base accesible por [pyDAL](https://github.com/web2py/pydal) (PostgreSQL, SQL Server, MySQL, SQLite y más). Solo lee metadatos: nunca toca tus datos.

Repo: https://github.com/Trukitro/Etch-DB-Mapper

## Características

- **Escaneo rápido**: 4 consultas en total, sin importar cuántas tablas tenga la base (una base de 171 tablas pasó de 513 consultas a 4), con progreso por fases en pantalla.
- **Mapa relacional** (Cytoscape.js): enfoque al pasar el mouse, panel de detalle, colores por grupo de tablas, alcance «relacionadas / todas / vecindad de una tabla», varios layouts, arrastrar y soltar con posiciones que se recuerdan, exportar a PNG.
- **Explorador**: búsqueda por tabla o columna, filtros (con relaciones, huérfanas, sin PK), insignias PK/FK, copiar DDL aproximado.
- **Resumen**: totales, tablas más conectadas, grupos de tablas, calidad del esquema, exportar a JSON.
- **Tu URI nunca se pierde**: la conexión se guarda antes de escanear, aunque falle. Renombrar y editar desde el menú.
- **Ayuda y Novedades** dentro de la app, pensadas para usuarios nuevos.
- Tema oscuro / claro / del sistema, atajos de teclado, 100 % offline.

## Instalación

### Windows (recomendado)
Descargá el instalador `Etch-DB-Mapper-Setup-vX.Y.Z.exe` (o el `.exe` portable) desde [Releases](https://github.com/Trukitro/Etch-DB-Mapper/releases). Requiere el *Microsoft Edge WebView2 Runtime*, que ya viene con Windows 11 y con Windows 10 actualizado.

### Desde el código
Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python db_manager_app.py
```

Opciones: `--debug` (DevTools con clic derecho → Inspeccionar), `--data-dir RUTA` (otra carpeta de datos, útil para pruebas).

## Uso básico

1. **Nueva conexión** → nombre, tipo de base (PostgreSQL, SQL Server, MySQL, SQLite) y servidor/usuario/contraseña. ¿Prefieres la URI? Pestaña *URI avanzada*, por ejemplo `postgres://usuario:clave@host:5432/base`.
2. **Guardar y escanear**.
3. Explorá las pestañas **Resumen**, **Explorador** y **Mapa**.

Más ejemplos de URI por motor, atajos y solución de problemas: [`HELP.md`](HELP.md) (también dentro de la app, en *Ayuda*). ¿Primera vez? Probá el botón **Probar con una base de ejemplo**.

## Estructura del proyecto

```
db_manager_app.py     Lanzador: crea la ventana pywebview y expone la API
core/
  api.py              API que ve la UI (window.pywebview.api.*) + eventos de escaneo
  scanner.py          Lectores de esquema por motor (pyDAL) y utilidades
  uri.py              Asistente de conexión: armar y descomponer URI
  storage.py          Persistencia JSON (conexiones y ajustes), escritura atómica
  paths.py            Rutas por sistema operativo y recursos empaquetados
  demo.py             Base SQLite de ejemplo
  version.py          Versión única de la app
webui/                Interfaz: HTML + CSS + JS sin build (Cytoscape vendorizado)
tests/                Pruebas unitarias (unittest)
tools/build_windows.ps1   Pruebas + .exe (PyInstaller) + instalador (Inno Setup)
installer/setup.iss   Script del instalador de Windows
docs/                 Arquitectura, roadmap, backlog, bugs, plan de Linux
```

Detalle técnico en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Desarrollo

```bash
python -m unittest discover -s tests -t .     # pruebas
python -m http.server 8765                     # UI en el navegador con API simulada:
                                               #   http://localhost:8765/webui/index.html
```

Compilar para Windows (`.exe` en `dist\`, instalador en `installer\output\`):

```powershell
.\tools\build_windows.ps1 -Installer
```

## Plataformas

| Plataforma | Estado |
|---|---|
| Windows 10/11 | Soportado (instalador y `.exe` portable) |
| Linux | En planificación — ver [`docs/LINUX_PLAN.md`](docs/LINUX_PLAN.md). El código ya es multiplataforma; falta el empaquetado y probarlo. |
| macOS | Sin planes, aunque el código no depende de Windows. |

## Documentación

- [`HELP.md`](HELP.md) — guía de uso.
- [`CHANGELOG.md`](CHANGELOG.md) — novedades por versión.
- [`docs/`](docs/) — arquitectura, backlog, bugs y planes.
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — componentes de terceros y sus licencias.

## Estado

Proyecto público, independiente de cualquier entorno de trabajo. No incluye credenciales, URIs ni datos reales de ningún cliente: solo datos de prueba generados.
