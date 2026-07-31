# Backlog — Etch-DB-Mapper

Mejoras planeadas, sin fecha fija. Mover a "En progreso"/"Hecho" a mano según se
vaya trabajando.

## Alta prioridad
_(vacío por ahora)_

## Media prioridad
- [ ] Agregar tests automatizados mínimos (más allá de `test_syntax.py`, que
      solo valida sintaxis) para `core/scanner.py` y `core/storage.py`.
- [ ] Indicador visual de "cuál DB está seleccionada" en el Historial de DBs
      (ya existe para las tarjetas de tabla dentro del Explorador, falta a
      nivel de conexión en la barra lateral).
- [ ] Botón para eliminar una conexión del historial (hoy solo se puede
      limpiar todo el archivo `db_maps.json` a mano).
- [ ] Recordar la preferencia de tema (claro/oscuro) entre sesiones — hoy
      siempre arranca en oscuro.

## Baja prioridad / exploración
- [ ] Evaluar cuáles layouts de mapa (radial, jerárquico, zonificado, tráfico,
      neural) de las versiones anteriores conviene ofrecer como opción en la
      UI actual.
- [ ] Exportar el mapa de relaciones a imagen (PNG/SVG) o PDF.
- [ ] Probar contra MySQL (Postgres y SQL Server ya verificados de verdad,
      contra bases reales — ver `BUGS.md` #2 y #15).
- [ ] Ajustar la posición de los nodos al cambiar el zoom (hoy el (x,y)
      guardado es independiente del zoom, así que con nodos más grandes a
      zoom alto pueden llegar a solaparse si no se los reacomodó a mano).
- [ ] Limpiar del historial las posiciones de tablas que ya no existen tras
      un rescan (hoy quedan guardadas sin usarse, no rompen nada pero son
      basura).

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
