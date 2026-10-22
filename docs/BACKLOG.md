# Backlog — Etch-DB-Mapper

Mejoras planeadas, sin fecha fija. Mover a "En progreso"/"Hecho" a mano según se
vaya trabajando.

## Alta prioridad
- [ ] **Verificar el scanner contra bases reales** (FKs de SQL Server, lectores de MySQL y las consultas de comentarios de SQL Server/MySQL de 2.3.0): la consulta nativa
      de FKs de SQL Server (`sys.foreign_key_columns`) y los lectores de
      PostgreSQL/MySQL están probados con SQLite y revisados a mano, pero hay
      que confirmarlos contra servidores reales (ver `BUGS.md` #19).
- [ ] Release 2.0.0 (tag + `.exe` + instalador) — pendiente de confirmación
      del autor antes de publicar.

## Media prioridad
- [x] ~~**Relaciones inferidas por nombre**~~ (hecho en 2.2.0) (ej. columna `ClienteID` ↔ tabla
      `Cliente`): muchas bases antiguas no declaran FKs (en la prueba real,
      121 de 171 tablas quedaban huérfanas). Mostrarlas en el mapa con otro
      estilo (línea punteada) y un interruptor para activarlas.
- [x] ~~Cifrar las URI guardadas~~ (hecho en 2.2.0 con DPAPI en Windows).
- [ ] Cifrado de contraseñas en **Linux/macOS** (libsecret / Keychain vía `keyring`); hoy la app
      indica que no cifra allí.
- [ ] Lectores de esquema nativos para más motores (Oracle, Firebird, DB2).
      Hoy se intenta `INFORMATION_SCHEMA` estándar. Ver
      `ARCHITECTURE.md` → «Agregar un lector de esquema».
- [ ] Probar MySQL/MariaDB contra un servidor real.
- [ ] Soporte de **Linux** (`LINUX_PLAN.md`): correr desde fuente, CI,
      AppImage / pip.
- [ ] Internacionalización (hoy la UI está solo en español).
- [x] ~~Capturas de pantalla en el README~~ (hecho en 2.2.0). Pendiente: un GIF corto de uso.

## Baja prioridad / exploración
- [ ] Exportar el mapa también a SVG/PDF (hoy solo PNG).
- [ ] Mostrar tipos y columnas dentro de los nodos del mapa (nodos «tarjeta»)
      cuando se hace zoom.
- [ ] Layouts adicionales (radial por tabla central, zonificado por prefijo de
      nombre, p. ej. `ETS_`, `Cat_`).
- [x] ~~Comparar dos escaneos de la misma conexión~~ (hecho en 2.2.0, pestaña Cambios).
- [ ] Detectar **renombres** de tablas/columnas en la comparación (hoy aparecen como quitar + agregar).
- [ ] Limpiar del historial las posiciones de tablas que ya no existen tras
      un rescan (no rompen nada, solo ocupan espacio).
- [x] ~~Aviso de versión nueva~~ (hecho en 2.2.0, opcional). Pendiente: descarga/actualización automática (decisión de seguridad).
- [ ] Permitir confirmar/descartar relaciones probables y guardarlas por conexión.

## Hecho
- [x] Separar el proyecto público del proyecto de trabajo (este repo).
- [x] Copiar y sanear el código base (sin `old_code/`, sin credenciales).
- [x] `git init` + primer commit + push al remote
      `https://github.com/Trukitro/Etch-DB-Mapper.git`.
- [x] Integrar icono y logo (`images/etch_db_icon.svg`, `etch_db_logo.svg`) en
      la app, el `.exe` y el instalador.
- [x] Empaquetar con PyInstaller → `.exe` standalone, assets embebidos
      (`--add-data`), sin depender de archivos sueltos junto al ejecutable.
- [x] Crear instalador wizard con Inno Setup
      (`installer/setup.iss` → `Etch-DB-Mapper-Setup-v1.0.0.exe`), probado con
      instalación y desinstalación silenciosa.
- [x] Publicar el release `v1.0.0` en GitHub con el `.exe` y el instalador
      como assets: https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.0.0
- [x] Datos de prueba locales disponibles (Postgres, no publicados — ver
      nota en `AGENTS.md`) para probar el scanner sin depender de una BD real
      de trabajo.
- [x] Soporte multi-DB básico: el query de tablas ya no depende del esquema
      `dbo` de SQL Server, funciona contra Postgres real (`BUGS.md` #2).
- [x] Corregido el JOIN de la consulta de Foreign Keys, que rompía el scan
      completo apenas una tabla tenía una FK (`BUGS.md` #3).
- [x] Implementado el editor de URI ("⚙️ URI"), que antes crasheaba en
      silencio por un método faltante (`BUGS.md` #4).
- [x] Detección de motor por prefijo de URI + mensaje claro si falta el driver
      Python correspondiente (`pyodbc`, `psycopg2`, etc.) en vez de una
      excepción cruda.
- [x] Reemplazados los `except:` desnudos en `core/storage.py` y
      `ui/main_ui.py` por manejo explícito (`BUGS.md` #5, #6).
- [x] `run_db_scan()` cierra la conexión `pydal` explícitamente en un
      `finally` (`BUGS.md` #7).
- [x] Publicado el release `v1.1.0` en GitHub con el `.exe` y el instalador
      actualizados: https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.1.0
- [x] Arreglado que el `.exe` instalado no podía guardar el historial
      (`PermissionError` en Program Files) — ahora usa `%LOCALAPPDATA%`
      (`BUGS.md` #10).
- [x] La URI se guarda de inmediato al hacer "Escanear", antes de intentar
      conectar — ya no se pierde si el escaneo falla (`BUGS.md` #11).
- [x] Corregida condición de carrera al editar+reintentar una conexión
      mientras un escaneo viejo del mismo alias seguía en vuelo
      (`BUGS.md` #12).
- [x] Mensajes de error acortados a la línea real de la excepción, en vez
      del traceback completo de Python (`BUGS.md` #13).
- [x] Indicadores de estado (✓ éxito / ⚠ error) por conexión en el
      Historial de DBs.
- [x] Agregadas ventanas de "Acerca de" y "Ayuda" (guía paso a paso) con
      botones en el footer de la barra lateral.
- [x] Eliminado código muerto: `ask_new_scan()` (`BUGS.md` #14).
- [x] Arreglado el crash por encoding de `test_syntax.py` en consolas
      cp1252 (`BUGS.md` #9).
- [x] Publicado el release `v1.2.0` en GitHub con el `.exe` y el instalador
      actualizados: https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.2.0
- [x] Mapa Relacional: arrastrar tablas a mano (drag & drop), con las líneas
      de conexión actualizándose en vivo. La posición de cada tabla se
      guarda en `history[db]["positions"]` y persiste entre sesiones.
- [x] Botón "🔄 Auto-Organizar" para descartar posiciones manuales y volver
      a correr el layout automático.
- [x] Controles de zoom movidos de la barra lateral al toolbar del Mapa
      Relacional (`[-] [100%] [+]` + slider), liberando espacio vertical
      para el Historial de DBs.
- [x] Resaltado por hover ("Focus Mode"): pasar el mouse sobre una tabla o
      una conexión atenúa el resto y resalta solo las relaciones activas.
- [x] Detección de Primary Key en `core/scanner.py` (antes solo se
      detectaban Foreign Keys). Nodos del mapa con badges 🔑 (PK) y 🔗 (FK)
      por columna, y estilo visual modernizado acorde a la marca.
- [x] Publicado el release `v1.3.0` en GitHub con el `.exe` y el instalador
      actualizados: https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.3.0
- [x] Explorador modernizado: tarjetas de tabla (ícono + nombre + cantidad
      de columnas + indicador 🔗 de relaciones) en vez de botones planos,
      con resaltado de la tarjeta seleccionada.
- [x] Reemplazado el `ttk.Treeview` de columnas (visualmente desentonaba
      con el resto de la app) por una lista propia con los mismos badges
      🔑/🔗 del Mapa Relacional, filas alternadas y tipos coloreados.
- [x] Dashboard de estadísticas (tablas / columnas / relaciones /
      huérfanas) al cargar una conexión.
- [x] Búsqueda mejorada: filtra por nombre de tabla o de columna, muestra
      cuántos resultados encontró y en qué columna matcheó.
- [x] Botón "📋 Copiar DDL": copia al portapapeles un `CREATE TABLE`
      aproximado de la tabla seleccionada (a partir de los tipos de
      `INFORMATION_SCHEMA`, no 100% ejecutable en todos los motores).
- [x] Selector de tema claro/oscuro (🌙/☀️ en el footer de la barra
      lateral). El canvas del Mapa Relacional se mantiene siempre oscuro
      a propósito.
- [x] Publicado el release `v1.4.0` en GitHub con el `.exe` y el instalador
      actualizados: https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.4.0
- [x] Corregido el placeholder de parámetro (`?` vs `%s`) según el motor —
      SQL Server (`pyodbc`) rompía en la primera tabla con "0 parameter
      markers, but 1 parameters were supplied". Verificado de verdad contra
      un SQL Server real (171 tablas) — antes nunca se había probado
      (`BUGS.md` #15).
- [x] Publicado el release `v1.5.0` en GitHub con el `.exe` y el instalador
      actualizados: https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.5.0

### 2.0.0 — reescritura a pywebview + HTML/CSS/JS
- [x] Migración completa de CustomTkinter a pywebview con HTML, CSS y JS
      (`STACK_EXPLORATION.md`). Backend en `core/` conservado y ampliado.
- [x] Notificaciones flotantes («toast») que no reservan espacio en el layout
      (`BUGS.md` #16).
- [x] Escaneo en 4 consultas en total (antes 3 por tabla) y progreso por
      fases en pantalla; la ventana ya no queda «No responde» (`BUGS.md` #17).
- [x] Renombrar conexiones (menú contextual / editar) con `id` estable
      (`BUGS.md` #18).
- [x] Mapa relacional nuevo con Cytoscape.js (fcose): alcance relacionadas /
      todas / vecindad, modo foco, panel de detalle, posiciones persistentes,
      exportar PNG.
- [x] Conexión a cualquier motor accesible por pyDAL (lectores nativos para
      PostgreSQL, SQL Server, MySQL y SQLite; genérico para el resto).
- [x] Páginas de **Ayuda** (`HELP.md`) y **Novedades** (`CHANGELOG.md`)
      dentro de la app, más pantalla de inicio para usuarios nuevos y base
      de ejemplo integrada.
- [x] Tema oscuro / claro / del sistema recordado entre sesiones.
- [x] Eliminar conexiones desde la barra lateral.
- [x] Tests automatizados (`tests/`, 28 pruebas) y `tools/build_windows.ps1`.
- [x] Carpeta de datos por sistema operativo y plan de Linux
      (`LINUX_PLAN.md`).

### 2.2.0 — seguridad, relaciones probables y cambios
- [x] Contraseñas cifradas con Windows DPAPI y migración automática (`SECURITY.md`).
- [x] Filtro de secretos en errores y en `etch.log`.
- [x] Relaciones probables por nombre (alta/media confianza) en mapa, resumen y explorador.
- [x] Historial de versiones del esquema y pestaña **Cambios** con resumen en Markdown.
- [x] Aviso de versión nueva opcional y pantalla de **Preferencias**.
- [x] Capturas en el README generadas con la app real (`tools/capture_screenshots.py`).

### 2.3.0 — documental
- [x] Diccionario de datos: notas, etiquetas y responsable por tabla; notas por columna; búsqueda y filtro *Sin documentar*.
- [x] Lectura de descripciones nativas (PostgreSQL, SQL Server, MySQL).
- [x] Exportar a Markdown, CSV e informe HTML interactivo autocontenido.
- [x] Pestaña Rutas: camino entre dos tablas y generador de JOIN; resaltado en el mapa.

### Ideas siguientes (documental / navegación)
- [ ] Exportar a Mermaid / PlantUML / DDL completo.
- [ ] Informe HTML con tema claro/oscuro seleccionable y filtro por etiqueta.
- [ ] Importar/exportar las notas (JSON) para compartirlas entre equipos o conexiones.
- [ ] «Dónde se usa esta columna»: columnas del mismo nombre en otras tablas.
- [ ] Revisión de calidad: FK sin índice, columnas del mismo nombre con distinto tipo.

### 2.4.0 — migración, fase 1
- [x] Pestaña Migrar: script de creación de tablas para PostgreSQL, SQL Server, MySQL y SQLite (`core/migrate.py`).
- [x] Metadatos extra en el escaneo: identidad, valores por defecto, precisión de decimales y UNIQUE.
- [x] Plan de las fases 2 y 3 con las reglas de seguridad (`MIGRATION_PLAN.md`).

### Migración — siguientes pasos
- [ ] **Probar los scripts de PostgreSQL, SQL Server y MySQL contra servidores reales** (hoy solo SQLite se ejecuta en las pruebas).
- [ ] Fase 2: copia de datos con origen en solo lectura impuesto por la base, destino obligatoriamente vacío, plan, simulacro y verificación.
- [ ] Índices no únicos, `CHECK` y reglas `ON DELETE/ON UPDATE` en el script.
- [ ] Elegir qué tablas migrar desde la interfaz (la API ya admite `only`).
- [ ] Informe de compatibilidad de vistas, procedimientos y triggers («revisar a mano»).
- [ ] Mapa de tipos editable por el usuario.

### 2.5.0 — migración, fase 2
- [x] Copiar datos a un destino vacío con origen en solo lectura, plan, simulacro, confirmación, cancelación y verificación de conteos (`core/copy_engine.py`).
- [x] Datos de muestra en la base de ejemplo.
- [x] Corregidas las comillas de PostgreSQL en el SQL de los JOIN.

### Migración — pendientes tras la fase 2
- [ ] **Probar la escritura** hacia PostgreSQL, SQL Server y MySQL y la lectura de SQL Server/MySQL contra servidores reales desechables.
- [ ] Reanudar una copia interrumpida y elegir qué tablas copiar desde la interfaz.
- [ ] Verificación con sumas de control además de los conteos.
- [ ] Copiar más rápido en bases grandes (`COPY` en PostgreSQL, `fast_executemany` en SQL Server).
- [ ] Informe de filas rechazadas en lugar de detener la copia en el primer error (modo opcional).
