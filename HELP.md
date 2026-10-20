# Guía de uso

Etch-DB-Mapper lee **solo el esquema** de tu base de datos —tablas, columnas, claves primarias y relaciones— y te lo muestra como un explorador buscable y un mapa interactivo. Nunca lee ni modifica los datos de tus tablas.

## Primeros pasos

1. **Creá una conexión.** Hacé clic en **Nueva conexión** (o `Ctrl+N`). Poné un nombre (por ejemplo `Producción`) y pegá la URI de tu base. Si querés solo mirar cómo funciona, usá **Probar con una base de ejemplo**.
2. **Guardala.** La conexión se guarda en tu equipo apenas tocás **Guardar**, aunque todavía no funcione. Si el escaneo falla, no hace falta volver a escribir nada: corregís y reintentás.
3. **Escaneá.** Con **Guardar y escanear** (o **Reescanear** más tarde) la app lee el esquema. Verás el progreso por fases y podés seguir usando la app mientras tanto.
4. **Explorá.** Cuando termina, aparecen tres pestañas: **Resumen**, **Explorador** y **Mapa**.

> Consejo: usá una cuenta de **solo lectura** de la base. Etch-DB-Mapper solo consulta metadatos, pero una cuenta limitada es siempre más segura.

## Cómo armar la URI

La URI sigue el formato de [pydal](https://py4web.com/_documentation/static/en/chapter-07.html): `motor://usuario:clave@host:puerto/base`.

| Motor | Ejemplo de URI | Driver necesario |
|---|---|---|
| PostgreSQL | `postgres://usuario:clave@host:5432/base` | `psycopg2-binary` |
| SQL Server | `mssql4://usuario:clave@host:1433/base?DRIVER={ODBC Driver 18 for SQL Server}` | `pyodbc` + driver ODBC de Microsoft |
| MySQL / MariaDB | `mysql://usuario:clave@host:3306/base` | `pymysql` |
| SQLite | `sqlite://C:/ruta/a/mi_base.db` | ya incluido en Python |

- En SQL Server, el parámetro `DRIVER=` indica qué driver ODBC usar. Los nombres habituales son `{ODBC Driver 18 for SQL Server}`, `{ODBC Driver 17 for SQL Server}` y `{SQL Server}`. Para ver cuáles tenés instalados, abrí **Orígenes de datos ODBC** en Windows, pestaña *Controladores*.
- Si la contraseña tiene caracteres como `@`, `/` o `:`, puede romper la URI. Lo más simple es usar una cuenta con una contraseña sin esos símbolos.
- Cualquier otro motor que pydal soporte se intenta con el `INFORMATION_SCHEMA` estándar; puede funcionar o no según el motor.
- Mientras escribís, la app te avisa si reconoce el motor y si falta instalar el driver.

## Dónde encontrar la información

### Resumen

Una vista general: cuántas tablas, columnas y relaciones hay, qué tablas están más conectadas, cuáles tienen más columnas y cuáles no tienen clave primaria. Hacé clic en una tarjeta para ir directo al detalle. Desde aquí también podés **exportar el esquema en JSON**.

### Explorador

- **Buscá** por nombre de tabla o de columna (`/` o `Ctrl+K` enfocan el buscador). Las flechas ↑ ↓ cambian de tabla.
- **Filtrá** por *Con relaciones*, *Huérfanas* (sin relaciones) o *Sin PK*, y ordená por nombre, columnas o relaciones.
- En el detalle de una tabla ves cada columna con su tipo, si admite nulos, y las insignias **PK** (clave primaria) y **FK** (clave foránea). Los nombres de tablas relacionadas son enlaces.
- Podés **copiar el nombre**, **copiar un DDL aproximado** (`CREATE TABLE …`) o saltar a la tabla en el mapa.

### Mapa

El mapa dibuja las tablas como nodos y las claves foráneas como flechas (`tabla_hija → tabla_padre`).

- **Pasá el mouse** sobre una tabla para enfocarla: se atenúa todo lo que no está conectado con ella.
- **Hacé clic** en una tabla para abrir el panel lateral con sus columnas y relaciones. **Doble clic** enfoca su vecindad.
- **Arrastrá** las tablas para ordenarlas a tu gusto: la posición se recuerda para esa conexión.
- **Alcance:** *Tablas con relaciones* (por defecto, lo más legible), *Todas las tablas* (las huérfanas quedan en una grilla aparte) o *Vecindad de una tabla* (una tabla y sus vecinas a 1, 2 o 3 saltos).
- **Auto-organizar** descarta las posiciones guardadas y vuelve a acomodar todo. **PNG** exporta una imagen del mapa.
- El **color** indica el grupo de tablas conectadas entre sí.

## Bases de datos grandes

- El escaneo hace pocas consultas (no una por tabla), así que bases de cientos de tablas terminan en segundos.
- Para un mapa legible, empezá con el alcance **Tablas con relaciones** o **Vecindad de una tabla**.
- Si la mayoría de las tablas aparecen como *huérfanas*, es normal en bases antiguas: el vínculo entre tablas existe solo por convención (por ejemplo, una columna `ClientID`) y no como FOREIGN KEY declarada. El Explorador y la búsqueda funcionan igual.

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+N` | Nueva conexión |
| `Ctrl+K` o `/` | Buscar tablas |
| `F5` | Reescanear la conexión actual |
| `Alt+1` `Alt+2` `Alt+3` | Resumen, Explorador, Mapa |
| `Ctrl+B` | Mostrar u ocultar la barra lateral |
| `?` | Abrir esta ayuda |
| `Esc` | Cerrar diálogos, limpiar la búsqueda |

## Tus datos y privacidad

- Las conexiones, los esquemas escaneados y las posiciones del mapa se guardan **solo en tu equipo**.
- La app no envía información a ningún servidor. Solo abre tu navegador cuando hacés clic en un enlace externo.
- Las contraseñas se muestran ocultas en pantalla, pero la URI completa se guarda en un archivo local sin cifrar. No compartas esa carpeta.
- **Windows:** `%LOCALAPPDATA%\Etch-DB-Mapper` · **Linux:** `~/.local/share/Etch-DB-Mapper` · **macOS:** `~/Library/Application Support/Etch-DB-Mapper`.

## Solución de problemas

**«Falta el driver…»** — Instalá el driver indicado (`pip install psycopg2-binary`, `pyodbc`, `pymysql`). En la versión instalada con el `.exe`, los drivers de Python para PostgreSQL, SQL Server y MySQL ya vienen incluidos; en SQL Server además hace falta el driver ODBC de Microsoft, que se instala aparte.

**SQL Server: «Data source name not found» o «driver not found».** — El nombre del `DRIVER=` no coincide con uno instalado. Revisá los nombres en *Orígenes de datos ODBC* y probá con `{ODBC Driver 17 for SQL Server}` o `{SQL Server}`.

**«Tiempo de espera agotado» / no conecta.** — Revisá host y puerto, que la base acepte conexiones remotas y que ningún firewall o VPN bloquee el acceso. Probá conectar con otra herramienta (por ejemplo `psql` o SSMS) para confirmar que no es un problema de red.

**«Login failed» / «password authentication failed».** — Usuario o contraseña incorrectos. Editá la conexión (menú `⋯` → *Editar conexión*) y corregí la URI.

**El mapa sale muy cargado.** — Cambiá el alcance a *Vecindad de una tabla*, o usá *Tablas con relaciones* en lugar de *Todas*. Pasar el mouse por una tabla ayuda a seguir sus conexiones.

**La app no abre en Windows.** — Hace falta el *Microsoft Edge WebView2 Runtime*, que viene con Windows 11 y con Windows 10 actualizado. Si falta, descargalo desde Microsoft e instalalo.

**¿Algo más?** — Copiá el mensaje de error (hay un botón **Copiar detalle**) y abrí un reporte en el repositorio. El registro técnico se guarda en `etch.log` dentro de la carpeta de datos.

## Preguntas frecuentes

**¿Puedo renombrar una conexión?** Sí: clic derecho (o menú `⋯`) sobre ella → *Renombrar*. El esquema y las posiciones del mapa se conservan.

**¿Qué pasa si escaneo de nuevo?** Se reemplaza el esquema guardado por el nuevo. Las posiciones del mapa se mantienen y las tablas nuevas se acomodan solas.

**¿Funciona sin internet?** Sí, todo el mapa y la interfaz son locales.

**¿Y en Linux o macOS?** El código es multiplataforma y la carpeta de datos sigue las convenciones de cada sistema; el instalador y el empaquetado oficiales por ahora son para Windows. El plan para Linux está en `docs/LINUX_PLAN.md`.
