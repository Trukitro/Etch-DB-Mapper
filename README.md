# Etch-DB-Mapper

**Etch-DB-Mapper** lee el esquema de una base de datos —tablas, columnas, claves y relaciones— y te lo muestra como un explorador buscable y un mapa interactivo. Funciona con cualquier base accesible por [pyDAL](https://github.com/web2py/pydal) (PostgreSQL, SQL Server, MySQL, SQLite y más). Solo lee metadatos: nunca toca tus datos.

Repo: https://github.com/Trukitro/Etch-DB-Mapper

![Mapa relacional](docs/images/04-mapa.png)

## 🔒 Seguridad y privacidad (lo que tienes que saber)

- **Tus contraseñas se guardan cifradas.** En Windows se cifran con **DPAPI**, ligadas a tu usuario y a tu equipo: no hay ninguna contraseña en claro en el disco, y copiar el archivo a otra PC no las revela. Las conexiones guardadas con versiones anteriores se cifran solas al actualizar.
- **Solo lectura.** Para mapear, la app consulta únicamente el catálogo del motor (tablas, columnas, claves); no lee el contenido de tus tablas. **Solo si usas «Copiar datos»** lee las filas del origen —siempre en modo solo lectura— y escribe en un destino nuevo o vacío que tú eliges; nunca modifica el origen.
- **Cero telemetría.** No envía tus datos, tus URI ni tus esquemas a ningún servidor. Todo vive en tu carpeta de datos.
- **Aviso de versión nueva, opcional y transparente.** Una consulta pública a GitHub, como máximo una vez al día, sin datos tuyos y sin instalar nada solo. Se apaga en *Preferencias* o con `ETCH_NO_UPDATE_CHECK=1`.
- **Sin secretos en los registros ni en los errores**, y una interfaz que no ejecuta código remoto.

Detalle completo —incluido lo que el cifrado **no** puede proteger— en [`SECURITY.md`](SECURITY.md). Recomendación: usa siempre una **cuenta de solo lectura** en tus bases.

## Características

- **Asistente de conexión**: elige el tipo de base (PostgreSQL, SQL Server, MySQL, SQLite), completa servidor, usuario y contraseña, **prueba la conexión** y listo. La URI de pydal sigue disponible para quien la prefiere.
- **Escaneo rápido**: un número fijo de consultas (4 más hasta 3 opcionales: descripciones, detalles de columnas y UNIQUE), sin importar cuántas tablas tenga la base (una de 171 tablas pasó de 513 consultas a 4), con progreso por fases.
- **Mapa relacional** (Cytoscape.js): enfoque al pasar el mouse, panel de detalle, colores por grupo de tablas, alcance «relacionadas / todas / vecindad», varios layouts, posiciones que se recuerdan, exportar a PNG.
- **Relaciones probables por nombre**: muchas bases antiguas no declaran claves foráneas. La app deduce `Pedidos.ClienteID → Clientes` por nombres y tipos y las dibuja con línea punteada, siempre como *sugerencias* y con interruptor.
- **Cambios entre escaneos**: cada vez que el esquema cambia se guarda una versión; compáralas y ve qué tablas, columnas y relaciones se agregaron, quitaron o modificaron (con resumen copiable en Markdown).
- **Diccionario de datos**: documenta tus tablas y columnas con notas, etiquetas y responsables (se guardan en tu equipo y sobreviven a los reescaneos). La app también lee las **descripciones que la base ya tiene** (`COMMENT ON`, `MS_Description`, `COMMENT=`). Exporta a **Markdown**, **Excel (CSV)** o a un **informe HTML interactivo de un solo archivo**, con el mapa incluido, para compartir sin que el otro instale nada.
- **Rutas entre tablas**: «¿cómo uno `Pedidos` con `Conductores`?». Encuentra los caminos por claves foráneas (y relaciones probables) y genera el **SQL del JOIN** listo para copiar, para SQL Server, PostgreSQL, MySQL y SQLite. Solo genera texto: no ejecuta nada.
- **Migrar a otro motor**:
  - **Script de esquema:** genera el SQL de creación de tablas para PostgreSQL, SQL Server, MySQL o SQLite (tipos traducidos, claves primarias y foráneas, UNIQUE, identidades, valores por defecto y descripciones) con un informe de advertencias. Solo genera texto: no se conecta al destino.
  - **Copiar datos:** copia los datos a otra base **nueva o vacía**, con el **origen en solo lectura** (impuesto por la propia base en PostgreSQL, MySQL y SQLite), un plan previo que no escribe nada, un simulacro, confirmación escribiendo el nombre del destino, todo o nada por tabla y verificación de conteos. **Nada se borra ni se sobrescribe**, y si el destino tiene cualquier conflicto, se niega. Detalle en [`docs/MIGRATION_PLAN.md`](docs/MIGRATION_PLAN.md).
- **Explorador** con búsqueda por tabla, columna o nota, filtros (incluido *Sin documentar*), insignias PK/FK y copia de DDL aproximado.
- **Ayuda y Novedades** dentro de la app, pensadas para usuarios nuevos. Tema oscuro / claro / del sistema, atajos de teclado, 100 % offline.

## Capturas

| | |
|---|---|
| ![Asistente de conexión](docs/images/08-asistente-conexion.png) **Asistente de conexión** | ![Resumen](docs/images/02-resumen.png) **Resumen del esquema** |
| ![Relaciones probables](docs/images/06-mapa-relaciones-probables.png) **Relaciones probables** (línea punteada) en una base sin claves foráneas | ![Cambios](docs/images/07-cambios.png) **Cambios entre dos escaneos** |
| ![Documentación](docs/images/11-documentacion.png) **Diccionario de datos**: notas, etiquetas y responsable | ![Rutas](docs/images/12-rutas.png) **Rutas entre tablas** con el SQL del JOIN |
| ![Informe HTML](docs/images/13-informe-html.png) **Informe HTML** interactivo de un solo archivo | ![Preferencias y seguridad](docs/images/09-preferencias.png) **Preferencias**: contraseñas cifradas y actualizaciones |
| ![Migración](docs/images/14-migracion.png) **Migrar a otro motor**: opciones, advertencias y tipos | ![Script de migración](docs/images/15-migracion-script.png) **Script SQL** generado para SQL Server |
| ![Plan de copia](docs/images/16-copia-plan.png) **Copiar datos**: plan previo sin escribir nada | ![Resultado de la copia](docs/images/17-copia-resultado.png) **Copia verificada** tabla por tabla |
| ![Explorador](docs/images/03-explorador.png) **Explorador de tablas** | |

## Instalación

### Windows (recomendado)
Descarga el instalador `Etch-DB-Mapper-Setup-vX.Y.Z.exe` (o el `.exe` portable) desde [Releases](https://github.com/Trukitro/Etch-DB-Mapper/releases). Requiere el *Microsoft Edge WebView2 Runtime*, que ya viene con Windows 11 y con Windows 10 actualizado.

### Desde el código
Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python db_manager_app.py
```

Opciones: `--debug` (DevTools con clic derecho → Inspeccionar), `--data-dir RUTA` (otra carpeta de datos, útil para pruebas).

## Uso básico

1. **Nueva conexión** → nombre, tipo de base y servidor / usuario / contraseña. ¿Prefieres la URI? Pestaña *URI avanzada*, por ejemplo `postgres://usuario:clave@host:5432/base`.
2. **Probar conexión** y **Guardar y escanear**.
3. Explora **Resumen**, **Explorador**, **Mapa**, **Rutas**, **Cambios** y **Migrar**; documenta tus tablas y exporta el diccionario cuando quieras.

Más ejemplos de URI por motor, atajos y solución de problemas: [`HELP.md`](HELP.md) (también dentro de la app, en *Ayuda*). ¿Primera vez? Prueba el botón **Probar con una base de ejemplo**.

## Estructura del proyecto

```
db_manager_app.py     Lanzador: crea la ventana pywebview y expone la API
core/
  api.py              API que ve la UI (window.pywebview.api.*) + eventos de escaneo
  scanner.py          Lectores de esquema por motor (pyDAL) y utilidades
  uri.py              Asistente de conexión: armar y descomponer URI
  secrets.py          Cifrado de contraseñas (Windows DPAPI)
  storage.py          Persistencia JSON atómica, contraseñas cifradas, historial de versiones
  inference.py        Relaciones probables por nombre
  joins.py            Caminos entre tablas y generador de JOIN
  docs_export.py      Diccionario de datos: Markdown, CSV e informe HTML
  migrate.py          Migración: script de esquema para otro motor
  copy_engine.py      Migración: copia de datos (origen solo lectura, destino vacío)
  diff.py             Comparación de dos versiones del esquema
  updates.py          Aviso de versión nueva (opcional)
  logs.py             Registro sin contraseñas
  paths.py, demo.py, version.py
webui/                Interfaz: HTML + CSS + JS sin build (Cytoscape vendorizado)
tests/                Pruebas unitarias (unittest)
tools/                build_windows.ps1 (exe + instalador), capture_screenshots.py
installer/setup.iss   Script del instalador de Windows
docs/                 Arquitectura, roadmap, backlog, bugs, plan de Linux, imágenes
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

Regenerar las capturas de `docs/images/` con la app real y datos de demostración: `python tools/capture_screenshots.py`.

## Plataformas

| Plataforma | Estado |
|---|---|
| Windows 10/11 | Soportado (instalador y `.exe` portable). Contraseñas cifradas con DPAPI. |
| Linux | En planificación — ver [`docs/LINUX_PLAN.md`](docs/LINUX_PLAN.md). El código ya es multiplataforma; falta el empaquetado, probarlo y un almacén de contraseñas. Mientras tanto **no cifra** las contraseñas allí y lo indica en *Preferencias*. |
| macOS | Sin planes, aunque el código no depende de Windows. |

## Documentación

- [`HELP.md`](HELP.md) — guía de uso.
- [`SECURITY.md`](SECURITY.md) — seguridad y privacidad, en detalle.
- [`CHANGELOG.md`](CHANGELOG.md) — novedades por versión.
- [`docs/`](docs/) — arquitectura, backlog, bugs y planes.
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — componentes de terceros y sus licencias.

## Estado

Proyecto público, independiente de cualquier entorno de trabajo. No incluye credenciales, URIs ni datos reales de ningún cliente: las capturas usan bases de demostración generadas por el propio proyecto.
