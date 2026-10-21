# Seguridad y privacidad

Etch-DB-Mapper maneja credenciales de bases de datos, así que esta página dice con claridad **qué protege, cómo y qué no puede proteger**. Si algo de lo que lees aquí no coincide con el comportamiento de la app, es un bug: por favor repórtalo.

## En resumen

| | |
|---|---|
| **Tus datos** | La app **solo lee metadatos** del catálogo (tablas, columnas, claves). Nunca lee ni modifica el contenido de tus tablas. |
| **Contraseñas guardadas** | Se guardan **cifradas con Windows DPAPI**, ligadas a tu usuario de Windows y a tu equipo. En el disco no hay ninguna contraseña en claro. |
| **Red** | La app **no tiene telemetría ni envía tus datos a ningún servidor**. Solo habla con tus bases y, opcionalmente, consulta una vez al día si hay una versión nueva en GitHub (ver más abajo). |
| **Todo es local** | Conexiones, esquemas, historial de versiones y ajustes viven en tu carpeta de datos. |

## Contraseñas guardadas

- Al guardar una conexión con contraseña, la URI completa se cifra con **DPAPI** (`CryptProtectData`, con una sal propia de la app) y en `db_maps.json` solo queda `uri_enc` (el dato cifrado) y una `uri` con la contraseña oculta (`usuario:••••@host`).
- Las conexiones guardadas con versiones anteriores (que tenían la contraseña en claro) **se cifran automáticamente** la primera vez que abres la 2.2 o posterior.
- Si copias `db_maps.json` a otro equipo u otro usuario de Windows, **no se puede descifrar**: la app lo detecta, no se bloquea y te pide volver a escribir la contraseña.
- En pantalla la contraseña siempre se muestra oculta; solo se ve si tú pulsas el ojo al editar la conexión.
- Los mensajes de error y el registro (`etch.log`) pasan por un filtro que elimina contraseñas (`PWD=…`, `usuario:clave@`) antes de mostrarse o guardarse.
- **Linux y macOS:** todavía no hay un almacén de credenciales integrado, así que la app **no cifra** las contraseñas allí y lo dice en *Preferencias → Seguridad* en lugar de aparentar lo contrario. Está planificado (ver `docs/LINUX_PLAN.md`).

### Lo que esto NO cubre (modelo de amenazas honesto)

DPAPI protege contra quien se lleve el archivo (copias de seguridad, un disco robado, un archivo compartido por error, otro usuario del equipo). **No** protege contra:

- Programas maliciosos que corran **con tu mismo usuario de Windows**: pueden pedirle a DPAPI que descifre, igual que lo hace la app.
- Alguien con tu sesión de Windows abierta.
- La contraseña mientras la app está en uso: está en memoria el tiempo necesario para conectarse.

Por eso recomendamos, además: usar **cuentas de solo lectura** en las bases, no reutilizar contraseñas y mantener Windows y el antivirus al día.

## Qué consulta la app en tu base

Solo el catálogo del motor (`INFORMATION_SCHEMA`, `sys.*`, `pragma_*` de SQLite). Son consultas fijas, sin parámetros ni texto tuyo concatenado en el SQL, y un número constante de ellas (no una por tabla). El código está en `core/scanner.py`. La opción *Probar conexión* ejecuta un `SELECT 1`.

## Conexiones de red

1. **Tus bases de datos**, a los servidores que tú configures.
2. **Búsqueda de versión nueva (opcional):** una petición `GET` pública a `api.github.com/repos/Trukitro/Etch-DB-Mapper/releases/latest`, como máximo **una vez al día**. No lleva datos tuyos ni de tus bases; solo lo que cualquier petición HTTP lleva (tu IP y el `User-Agent` `Etch-DB-Mapper/<versión>`). Nunca descarga ni instala nada: avisa y, si haces clic, abre la página del release en tu navegador. Se apaga en *Preferencias → Actualizaciones* o con la variable de entorno `ETCH_NO_UPDATE_CHECK=1`. El código está en `core/updates.py`.

No hay analítica, informes de errores automáticos ni cuentas.

## La interfaz

La ventana carga solo archivos locales (con una política CSP estricta, sin scripts remotos: Cytoscape.js va incluido en el paquete) y habla con Python solo por un puente interno. Los nombres de tablas y columnas se insertan siempre como texto, nunca como HTML. El enlace que abre la app en tu navegador solo acepta `http(s)`.

## Cómo reportar un problema de seguridad

Abre un *Security Advisory* privado en GitHub (pestaña **Security → Report a vulnerability** de https://github.com/Trukitro/Etch-DB-Mapper) o, si no está disponible, un issue **sin incluir credenciales ni datos reales**. Intentaré responder lo antes posible. Gracias por ayudar a que la app sea más segura.
