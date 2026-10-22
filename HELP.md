# Guía de uso

Etch-DB-Mapper lee **solo el esquema** de tu base de datos —tablas, columnas, claves primarias y relaciones— y te lo muestra como un explorador buscable y un mapa interactivo. Nunca lee ni modifica los datos de tus tablas.

## Primeros pasos

1. **Creá una conexión.** Hacé clic en **Nueva conexión** (o `Ctrl+N`). Poné un nombre (por ejemplo `Producción`), elegí el tipo de base y completá servidor, usuario y contraseña (o pegá una URI en la pestaña *URI avanzada*). Si querés solo mirar cómo funciona, usá **Probar con una base de ejemplo**.
2. **Guardala.** La conexión se guarda en tu equipo apenas tocás **Guardar**, aunque todavía no funcione. Si el escaneo falla, no hace falta volver a escribir nada: corregís y reintentás.
3. **Escaneá.** Con **Guardar y escanear** (o **Reescanear** más tarde) la app lee el esquema. Verás el progreso por fases y podés seguir usando la app mientras tanto.
4. **Explorá.** Cuando termina, aparecen tres pestañas: **Resumen**, **Explorador** y **Mapa**.

> Consejo: usá una cuenta de **solo lectura** de la base. Etch-DB-Mapper solo consulta metadatos, pero una cuenta limitada es siempre más segura.

## Cómo conectarte

Al crear o editar una conexión tenés dos formas, en las pestañas del diálogo:

- **Asistente** (recomendado): elegí el **tipo de base de datos** (PostgreSQL, SQL Server, MySQL / MariaDB o SQLite) y completá servidor, puerto, base, usuario y contraseña. La app arma la URI por vos y la muestra abajo (con la contraseña oculta). El puerto ya viene con el valor habitual si lo dejás vacío.
  - En **SQL Server** se detectan los drivers ODBC instalados y se elige el más nuevo; si el servidor usa un certificado autofirmado, marcá *Confiar en el certificado del servidor*.
  - En **SQLite** elegís el archivo con el botón.
- **URI avanzada**: escribís o pegás la URI de [pydal](https://py4web.com/_documentation/static/en/chapter-07.html) tal cual (`motor://usuario:clave@host:puerto/base`). Es la opción para otros motores y para quien prefiere el texto. Podés pasar de una pestaña a la otra: la URI se descompone en campos y viceversa.

Con **Probar conexión** verificás driver, red y credenciales en segundos, sin guardar ni escanear.

### Ejemplos de URI

| Motor | Ejemplo | Driver necesario |
|---|---|---|
| PostgreSQL | `postgres://usuario:clave@host:5432/base` | `psycopg2-binary` |
| SQL Server | `mssql4://usuario:clave@host:1433/base?DRIVER={ODBC Driver 18 for SQL Server}` | `pyodbc` + driver ODBC de Microsoft |
| MySQL / MariaDB | `mysql://usuario:clave@host:3306/base` | `pymysql` |
| SQLite | `sqlite://C:/ruta/a/mi_base.db` | ya incluido en Python |

- En SQL Server, `DRIVER=` indica qué driver ODBC usar (`{ODBC Driver 18 for SQL Server}`, `{ODBC Driver 17 for SQL Server}`, `{SQL Server}`). Con certificado autofirmado agregá `&TrustServerCertificate=yes`.
- Si la contraseña o el usuario tienen caracteres especiales (`@`, `:`, `/`, `%`), el Asistente los codifica solo. Escribiendo la URI a mano, usá la codificación con porcentaje: `@` = `%40`, `:` = `%3A`, `/` = `%2F`, `%` = `%25`.
- Cualquier otro motor que pydal soporte se intenta con el `INFORMATION_SCHEMA` estándar; puede funcionar o no según el motor.
- Mientras escribís en la pestaña avanzada, la app te avisa si reconoce el motor y si falta instalar el driver.

## Relaciones probables (bases sin claves foráneas)

Muchas bases, sobre todo las antiguas, **no declaran claves foráneas**: el vínculo entre tablas existe solo por convención (por ejemplo, `Pedidos.ClienteID` apunta a `Clientes`). Por eso el mapa podría verse casi vacío aunque la base tenga muchas relaciones.

Etch-DB-Mapper las **deduce por nombre y tipo** y las muestra como *relaciones probables*:

- **Alta confianza**: la columna se llama igual que la clave primaria de otra tabla (`CustomerID` en `Orders` y `Customers.CustomerID`) y los tipos son compatibles.
- **Media confianza**: el nombre de la columna sin su sufijo (`ID`, `Key`, `Cod`, `Codigo`, `Ref`…) coincide con el nombre de una tabla (con o sin prefijo como `tbl_`, en singular o plural).
- Si hay varias tablas posibles y no se puede decidir, **no se sugiere nada** (mejor omitir que equivocarse).

Son **sugerencias, no claves foráneas reales**: se dibujan con **línea punteada** (botón *Probables* en la barra del mapa), aparecen en el Resumen y en el detalle de cada tabla, y no cambian nada en tu base.

## Dónde encontrar la información

### Resumen

Una vista general: cuántas tablas, columnas y relaciones hay, qué tablas están más conectadas, cuáles tienen más columnas y cuáles no tienen clave primaria. Hacé clic en una tarjeta para ir directo al detalle. Desde aquí también podés **exportar el esquema en JSON**.

### Explorador

- **Buscá** por nombre de tabla o de columna (`/` o `Ctrl+K` enfocan el buscador). Las flechas ↑ ↓ cambian de tabla.
- **Filtrá** por *Con relaciones*, *Huérfanas* (sin relaciones) o *Sin PK*, y ordená por nombre, columnas o relaciones.
- En el detalle de una tabla ves cada columna con su tipo, si admite nulos, y las insignias **PK** (clave primaria) y **FK** (clave foránea). Los nombres de tablas relacionadas son enlaces.
- Podés **copiar el nombre**, **copiar un DDL aproximado** (`CREATE TABLE …`) o saltar a la tabla en el mapa.

### Documentar tus tablas (diccionario de datos)

En el **Explorador**, cada tabla tiene una tarjeta **Documentación** con una descripción, un **responsable** y **etiquetas**; cada columna tiene su propia descripción (botón ✎). Se guarda al salir del campo, **solo en tu equipo**, y sobrevive a los reescaneos.

- Si la base ya tiene descripciones (`COMMENT ON` en PostgreSQL, `MS_Description` en SQL Server, `COMMENT` en MySQL), las muestra con la marca *base*. Tu nota tiene prioridad sobre la de la base y nunca se escribe en ella.
- La búsqueda del Explorador también encuentra por nota, etiqueta o responsable, y el filtro **Sin documentar** te lleva a lo que falta.
- El **Resumen** muestra cuánto está documentado y los botones de exportación.

**Exportar** (Resumen → Documentación):

| Formato | Para qué sirve |
|---|---|
| **Markdown** | Pegarlo en un repositorio o wiki. |
| **Excel (CSV)** | Una fila por columna; se abre directo en Excel. |
| **Informe HTML** | Un solo archivo con el diccionario y el **mapa interactivo** (con tu disposición del mapa y las relaciones probables). Se abre en cualquier navegador, sin instalar nada: ideal para mandarlo a un colega. |

Los informes contienen **nombres de tablas y columnas, tipos, relaciones y tus notas**. **No** incluyen datos de las tablas, URI ni contraseñas. Revisa el contenido antes de compartirlo.

### Rutas entre tablas

La pestaña **Rutas** responde «¿cómo uno la tabla A con la tabla B?». Elige origen y destino (o usa **Camino hasta…** en el Explorador) y verás los caminos más cortos por claves foráneas, con claves reales primero y, si quieres, también relaciones probables. Cada camino trae el **SQL del JOIN** para copiar y un botón para **resaltarlo en el mapa**. La app solo genera el texto; no ejecuta nada en tu base. Los caminos con relaciones probables llevan una advertencia en el SQL.

### Migrar a otro motor

La pestaña **Migrar** lleva las tablas de la conexión actual a otro motor (PostgreSQL, SQL Server, MySQL / MariaDB o SQLite). Tiene dos modos:

#### Script de esquema (solo texto)

1. **Elige el motor de destino**, ajusta las **opciones** si quieres (esquema nuevo o prefijo para aislar lo migrado, estilo de nombres, qué incluir) y pulsa **Generar script**.
2. Verás el resumen, las **advertencias**, **cómo se traduce cada columna** y el script, que puedes copiar o guardar como `.sql`.
3. Tú lo ejecutas en una base **nueva o vacía** del destino. El script **solo crea objetos** (sin `DROP`, `TRUNCATE`, `DELETE` ni `UPDATE`, y sin `IF NOT EXISTS`: si algo ya existe, falla en vez de pisarlo).

Cada tipo o valor por defecto que no se puede traducir con seguridad se omite y se avisa; la app nunca adivina. No se migran índices no únicos, `CHECK`, reglas `ON DELETE/ON UPDATE`, vistas, procedimientos ni triggers.

#### Copiar datos

Para que la app **copie también los datos**:

1. **Crea antes la conexión de la base de destino** (*Nueva conexión*): debe ser una base **nueva o vacía**.
2. En *Migrar → Copiar datos* elige esa conexión como destino y, si el destino ya tiene otras tablas, define un **esquema nuevo** o un **prefijo** para no mezclar.
3. Pulsa **Revisar (no escribe nada)**. La app comprueba el destino y cuenta las filas del origen. Si hay cualquier conflicto —tablas con el mismo nombre, un destino con tablas y sin esquema/prefijo, un esquema que ya existe— **se niega** y te dice por qué.
4. Opcional pero recomendado: **Simulacro**. Lee todo el origen y comprueba que cada valor se puede convertir, **sin escribir nada**.
5. **Copiar datos…**: te pide escribir el nombre del destino para confirmar. La copia crea las tablas, carga los datos en orden (primero las tablas padre), agrega las claves foráneas al final y **verifica los conteos**. Puedes **cancelar** en cualquier momento.

Garantías y límites:

- **El origen solo se lee.** En PostgreSQL (transacción de solo lectura con foto consistente), MySQL y SQLite lo impone la propia base. En SQL Server no existe ese modo de sesión: la app solo emite `SELECT` y rechaza cualquier otra sentencia; usa un login de solo lectura.
- **En el destino solo se crea.** Nunca se borra ni se sobrescribe nada. Si una tabla falla, sus filas se revierten y la copia se detiene; las tablas ya terminadas quedan. En MySQL y SQLite el `CREATE TABLE` no se revierte: la tabla fallida queda creada pero vacía (la app te lo dice y no la borra).
- Si algo falla, el informe indica qué tablas terminaron y por qué se detuvo. Los valores de tus datos no se escriben en el registro (`etch.log`).
- **Si la base de origen está en uso** mientras copias, los conteos pueden no coincidir (en PostgreSQL la foto es consistente). Lo ideal es copiar desde una base sin escrituras o desde un respaldo.
- Copiar es más lento en bases muy grandes (se lee y escribe por lotes de 1000 filas). Esta versión copia tablas completas, sin reanudar copias interrumpidas.
- **Prueba primero con una base de destino desechable.** La copia está verificada de punta a punta con SQLite y leyendo desde un PostgreSQL real; la escritura hacia PostgreSQL, SQL Server y MySQL está cubierta por pruebas que no necesitan servidor, pero **no se ha ejecutado contra servidores reales**.

Más detalle de diseño en `docs/MIGRATION_PLAN.md` del repositorio.

### Cambios

La pestaña **Cambios** compara dos versiones del esquema de la misma conexión. Cada vez que reescaneas y el esquema es distinto, se guarda una versión nueva (se conservan las últimas 8). Verás qué **tablas, columnas y relaciones** se agregaron, quitaron o modificaron (tipo, nulabilidad, clave primaria), con un resumen que puedes copiar en Markdown. Tras un escaneo que encuentra diferencias, la app te avisa. Es ideal para detectar qué cambió en una base entre dos despliegues.

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
| `Alt+1` … `Alt+6` | Resumen, Explorador, Mapa, Rutas, Cambios, Migrar |
| `Ctrl+B` | Mostrar u ocultar la barra lateral |
| `?` | Abrir esta ayuda |
| `Esc` | Cerrar diálogos, limpiar la búsqueda |

## Tus datos y privacidad

- Las conexiones, los esquemas escaneados, el historial de versiones y las posiciones del mapa se guardan **solo en tu equipo**.
- **Las contraseñas se guardan cifradas** (en Windows, con DPAPI: solo las puede descifrar tu usuario de Windows en este equipo). Puedes comprobarlo en **Preferencias → Seguridad de las contraseñas**. Si copias la carpeta de datos a otro equipo, la app te pedirá escribir la contraseña de nuevo. En Linux/macOS todavía no hay cifrado y la app lo indica allí.
- La app **no envía tus datos ni tus URI a ningún servidor** y no tiene telemetría. Lo único que sale a internet, además de tus bases, es el **aviso de versión nueva** (opcional): una consulta pública a GitHub como máximo una vez al día. Se apaga en *Preferencias → Actualizaciones*.
- La app solo lee metadatos del catálogo; nunca el contenido de tus tablas. Usa de todos modos una **cuenta de solo lectura**.
- **Windows:** `%LOCALAPPDATA%\Etch-DB-Mapper` · **Linux:** `~/.local/share/Etch-DB-Mapper` · **macOS:** `~/Library/Application Support/Etch-DB-Mapper` (botón *Abrir* en Preferencias).
- Todos los detalles, incluido lo que el cifrado no puede proteger, están en `SECURITY.md` del repositorio.

## Preferencias

El engranaje de la barra lateral abre las **Preferencias**: tema, aviso de versión nueva (con botón *Buscar ahora*), estado del cifrado de contraseñas y acceso a la carpeta de datos.

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

**¿Funciona sin internet?** Sí: el mapa y la interfaz son locales. Solo el aviso de versión nueva necesita internet, y falla en silencio si no hay.

**¿Por qué no veo relaciones en mi base?** Probablemente no declara claves foráneas. Mira el botón **Probables** del mapa y la sección *Relaciones probables* más arriba.

**¿Cómo sé qué cambió en mi base?** Reescanea y abre la pestaña **Cambios**.

**¿Dónde se guardan mis notas?** En tu carpeta de datos (`annotations/`), nunca en la base. Si borras la conexión, se borran con ella.

**¿Cómo comparto el diccionario con alguien que no tiene la app?** Exporta el **Informe HTML** desde el Resumen y mándale el archivo.

**¿Y en Linux o macOS?** El código es multiplataforma y la carpeta de datos sigue las convenciones de cada sistema; el instalador y el empaquetado oficiales por ahora son para Windows. El plan para Linux está en `docs/LINUX_PLAN.md`.
