# Novedades

Historial de cambios de Etch-DB-Mapper. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones siguen [SemVer](https://semver.org/lang/es/).

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
