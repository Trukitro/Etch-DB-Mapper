# Novedades

Historial de cambios de Etch-DB-Mapper. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones siguen [SemVer](https://semver.org/lang/es/).

## [2.4.0] - 2026-10-22

### Nuevo
- **Pestaña Migrar** (`Alt+6`), fase 1 de la migración entre motores: genera el **script SQL de creación de tablas** para PostgreSQL, SQL Server, MySQL o SQLite con tipos traducidos, claves primarias y foráneas (también compuestas), UNIQUE, identidad/autoincremento, valores por defecto traducibles y descripciones (las de la base y tus notas).
- Informe de **advertencias** (errores, avisos, información) y vista de **cómo se traduce cada columna**.
- Opciones para aislar lo migrado: **esquema nuevo**, **prefijo** de tablas y estilo de nombres; incluir o no claves foráneas, UNIQUE, identidades, valores por defecto y descripciones. Guardar como `.sql` o copiar.
- El escaneo ahora lee también **precisión de decimales, identidades, valores por defecto y restricciones UNIQUE** (consultas opcionales de solo lectura: si fallan, el escaneo sigue igual). Verificado contra un PostgreSQL real.
- `docs/MIGRATION_PLAN.md`: diseño de las fases siguientes (copiar datos con el origen en solo lectura impuesto por la base y destino obligatoriamente vacío).

### Seguridad
- Esta fase **no se conecta a ningún destino ni escribe en ninguna base**. El script solo crea objetos nuevos: sin `DROP`, `TRUNCATE`, `DELETE`, `UPDATE`, `INSERT` ni `IF NOT EXISTS` (una prueba automática lo verifica para cada motor).

### Cambiado
- Las columnas de texto usadas como clave se acotan en SQL Server y MySQL (no admiten `MAX`/`TEXT` en una clave) y las claves foráneas heredan el mismo tipo que su tabla padre.
- El escaneo suma dos consultas opcionales (detalles de columnas y UNIQUE): hasta 7 en total.

## [2.3.0] - 2026-10-21

Versión «documental»: la app ahora sirve también para documentar y compartir lo que descubre.

### Nuevo
- **Diccionario de datos**: notas, etiquetas y responsable por tabla y notas por columna, guardados en tu equipo (sobreviven a los reescaneos). Búsqueda por documentación y filtro *Sin documentar*. El Resumen muestra el avance.
- **Descripciones nativas de la base**: se leen automáticamente (`COMMENT ON` en PostgreSQL, `MS_Description` en SQL Server, `COMMENT` en MySQL) y se muestran junto a tus notas. Es una consulta de solo lectura opcional: si el usuario no tiene permiso, el escaneo sigue igual.
- **Exportar el diccionario**: Markdown, Excel (CSV) e **informe HTML interactivo de un solo archivo** con el mapa incluido, para compartir sin instalar la app. Todo texto se escapa; no incluye datos de tablas ni credenciales.
- **Pestaña Rutas** (`Alt+5`): camino entre dos tablas por claves foráneas (y relaciones probables) con el **SQL del JOIN** para SQL Server, PostgreSQL, MySQL y SQLite; se puede resaltar en el mapa.
- Botón **Camino hasta…** en el Explorador.

### Cambiado
- El escaneo suma una consulta opcional para las descripciones de la base (5 en total en lugar de 4).

## [2.2.0] - 2026-10-21

### Seguridad
- **Contraseñas guardadas cifradas** con Windows DPAPI (ligadas a tu usuario y equipo). Las conexiones existentes se cifran solas la primera vez. Si el dato no se puede descifrar (otro usuario o equipo), la app lo detecta y pide escribir la contraseña de nuevo.
- Los mensajes de error y el registro (`etch.log`) ya no pueden contener contraseñas.
- Nuevo `SECURITY.md` con el modelo de amenazas, incluido lo que el cifrado no protege. En Linux/macOS la app indica que todavía no cifra.

### Nuevo
- **Relaciones probables por nombre**: para bases sin claves foráneas, la app deduce relaciones por nombres y tipos (con nivel de confianza) y las muestra con línea punteada en el mapa, en el Resumen y en el Explorador. Son sugerencias y tienen interruptor.
- **Pestaña Cambios**: compara dos versiones del esquema de una conexión (tablas, columnas, tipos, claves y relaciones), con resumen copiable en Markdown y aviso tras un escaneo con diferencias.
- **Aviso de versión nueva** (opcional, una consulta pública a GitHub como máximo por día; se apaga en Preferencias o con `ETCH_NO_UPDATE_CHECK=1`).
- **Preferencias**: tema, actualizaciones, estado del cifrado y acceso a la carpeta de datos. Atajo `Alt+4` para Cambios.
- Capturas de pantalla en el README (`tools/capture_screenshots.py` las regenera con datos de demostración).

### Cambiado
- Las URI con contraseña ya no se guardan en claro: en `db_maps.json` queda solo la versión cifrada y una URI con la contraseña oculta. Volver a una versión anterior a la 2.2 requeriría escribir de nuevo las contraseñas.

## [2.1.1] - 2026-10-21

### Corregido
- La ventana podía mostrar la interfaz de **otra aplicación** (por ejemplo otra app pywebview abierta al mismo tiempo) en lugar de Etch-DB-Mapper. Ambas compartían el puerto fijo 42001 del servidor interno; ahora Etch-DB-Mapper usa un puerto libre propio y no comparte caché del navegador.

## [2.1.0] - 2026-10-20

### Nuevo
- **Asistente de conexión**: elegí el tipo de base (PostgreSQL, SQL Server, MySQL / MariaDB, SQLite) y completá servidor, puerto, base, usuario y contraseña; la URI se arma sola. La pestaña **URI avanzada** sigue disponible y se puede alternar entre ambas sin perder datos.
- **Probar conexión**: verifica driver, red y credenciales sin guardar ni escanear, con mensajes claros (por ejemplo, si el servidor no responde).
- SQL Server: detección de los drivers ODBC instalados (se elige el más nuevo) y opción para confiar en certificados autofirmados.
- Puertos por defecto y vista previa de la URI con la contraseña oculta.

### Corregido
- Contraseñas con caracteres como `@`, `:` o `/` ya no rompen la URI: se codifican y se decodifican al conectar.

## [2.0.0] - 2026-10-20

Reescritura de la interfaz: de CustomTkinter a una interfaz web local (pywebview + HTML, CSS y JS). Más rápida, más clara y lista para crecer.

### Nuevo
- Interfaz moderna con tema oscuro, claro o del sistema, barra lateral colapsable y animaciones suaves.
- **Mapa relacional nuevo** con Cytoscape.js: modo foco al pasar el mouse, panel lateral, colores por grupo de tablas, alcance «solo relacionadas / todas / vecindad de una tabla», varios layouts y exportación a PNG. Las posiciones que arrastrás se recuerdan.
- **Pantalla de inicio y Ayuda** paso a paso para usuarios nuevos, con ejemplos de URI por motor, atajos de teclado y solución de problemas.
- **Novedades** (esta página) dentro de la app.
- Base de ejemplo integrada para probar la app sin conectarte a nada.
- Soporte para cualquier base accesible por pydal: lectores de esquema nativos para PostgreSQL, SQL Server, MySQL/MariaDB y SQLite, y lectura genérica por `INFORMATION_SCHEMA` para el resto.
- Renombrar conexiones desde el menú contextual, sin perder el esquema ni el mapa.
- Exportar el esquema completo a JSON desde el Resumen.
- Atajos de teclado: `Ctrl+N`, `Ctrl+K` o `/`, `F5`, `Alt+1/2/3`, `Ctrl+B`, `?`.
- Carpeta de datos acorde a cada sistema operativo (Windows, Linux y macOS) y plan de soporte para Linux en `docs/LINUX_PLAN.md`.

### Mejorado
- **Escaneo mucho más rápido**: 4 consultas en total en lugar de una por tabla (una base de 171 tablas pasó de 513 consultas a 4).
- Progreso del escaneo por fases con indicador y cronómetro; la ventana ya no se queda en «No responde» con bases grandes.
- Las notificaciones ahora flotan sobre la interfaz y se cierran solas: ya no dejan un hueco vacío.
- Las contraseñas de las URI se ocultan en pantalla.
- Guardado atómico de los datos y copia de seguridad automática si un archivo se corrompe.

### Compatibilidad
- Tus conexiones guardadas con la versión 1.x se leen sin cambios.

## [1.5.0] - 2026-07-25

### Corregido
- Escaneos de SQL Server fallaban con «0 parameter markers» por usar el estilo de parámetro incorrecto (`%s` en lugar de `?`).

## [1.4.0] - 2026-07-25

### Mejorado
- Explorador modernizado: tarjetas, insignias PK/FK, panel de resumen, búsqueda, copiar al portapapeles y alternar tema claro/oscuro.

## [1.3.0] - 2026-07-25

### Mejorado
- Mapa relacional: arrastrar y soltar con posiciones persistentes, modo foco, insignias PK/FK y botón Auto-organizar.

## [1.2.0] - 2026-07-24

### Nuevo
- Páginas de Ayuda y Acerca de.

### Corregido
- Error de escritura al instalar en Program Files: los datos ahora se guardan en la carpeta del usuario.
- La conexión se guarda antes de intentar conectar, así una URI que falla no se pierde.

## [1.1.0] - 2026-07-24

### Nuevo
- Detección de drivers faltantes con mensajes claros.
- Editor de URI.

### Corregido
- Escaneo de múltiples bases de datos.
- Manejo explícito de errores en lugar de bloques `except` vacíos.

## [1.0.0] - 2026-07-24

### Nuevo
- Primera versión pública: escaneo de esquemas de SQL Server, mapa relacional con Canvas, historial local en JSON, logo e icono, ejecutable e instalador para Windows.
