# Bugs conocidos — Etch-DB-Mapper

Detectados en una primera pasada de lectura de código al separar este proyecto
del original de trabajo, más los que fueron apareciendo al probar contra bases
reales. Los marcados [RESUELTO] ya están corregidos.

## 0. [RESUELTO] `self.tabs` usado antes de existir — crasheaba al arrancar
`setup_scan_panel()` (`ui/main_ui.py`) tenía un bloque duplicado al final que
volvía a crear las tabs (`self.tabs.add(...)`) y llamaba a
`setup_explorer_tab()`/`setup_mapper_tab()`/`setup_orphans_tab()` por segunda
vez. El problema: `setup_scan_panel()` se ejecuta desde `setup_layout()` antes
de que `self.tabs` exista (se crea unas líneas más abajo, ya en
`setup_layout()`), así que la app crasheaba en el arranque con
`AttributeError: '_tkinter.tkapp' object has no attribute 'tabs'` — tanto
corriendo `python db_manager_app.py` como en el `.exe` empaquetado. Se detectó
al probar el primer build con PyInstaller. Se borró el bloque duplicado; la
creación real de tabs en `setup_layout()` (líneas ~128-137) ya se encargaba de
esto correctamente.

## 1. [RESUELTO] Interpolación de nombre de tabla en SQL (core/scanner.py)
`core/scanner.py` construía la consulta de columnas con un f-string
(`WHERE TABLE_NAME = '{t}'`) en vez de parametrizarla como la consulta de
Foreign Keys de al lado. Se cambió a la misma forma parametrizada (`%s`).

## 2. [RESUELTO] Esquema hardcodeado a `'dbo'` — 0 tablas contra Postgres/otros motores
La consulta de tablas filtraba `WHERE TABLE_SCHEMA = 'dbo'`, el esquema por
defecto de SQL Server. Contra cualquier otro motor (Postgres usa `public`,
por ejemplo) el scan "funcionaba" (sin error) pero devolvía 0 tablas — muy
confuso para diagnosticar. Se cambió a excluir esquemas de sistema
(`information_schema`, `pg_catalog`, `sys`) en vez de exigir uno específico,
así funciona con el esquema por defecto de cualquier motor. Detectado y
verificado contra una base Postgres de prueba real (6 tablas, incluyendo
relaciones N:M y autorreferenciales).

## 3. [RESUELTO] JOIN incorrecto en la consulta de Foreign Keys — rompía el scan completo apenas había una FK
```sql
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE rel_kcu ON rc.UNIQUE_CONSTRAINT_NAME = rel_kcu.UNIQUE_CONSTRAINT_NAME
```
`KEY_COLUMN_USAGE` no tiene una columna `UNIQUE_CONSTRAINT_NAME` (esa
pertenece a `REFERENTIAL_CONSTRAINTS`) en ningún motor — esto nunca funcionó,
ni en SQL Server. Como el error ocurre *dentro* del `try` de `run_db_scan()`,
una sola tabla con FK abortaba el escaneo entero y descartaba todo lo ya
recolectado (`full_map`). Se corrigió el join a
`rc.UNIQUE_CONSTRAINT_NAME = rel_kcu.CONSTRAINT_NAME`.

## 4. [RESUELTO] `show_uri_editor()` no existía — "Editar URI" crasheaba en silencio
`edit_uri()` (`ui/main_ui.py`) llamaba a `self.show_uri_editor()`, un método
que nunca se implementó. Como corre dentro del hilo de UI directamente (no en
el hilo de escaneo con su propio try/except), la excepción no se mostraba
como notificación — simplemente no pasaba nada al hacer clic en "⚙️ URI". Se
implementó el panel (`uri_editor_frame` + `uri_edit_entry`) con guardar/
cancelar, verificado con un flujo completo: cargar URI existente, editarla,
guardar, y confirmar que persiste en el JSON de historial.

## 5. [RESUELTO] `except:` desnudo en `core/storage.py`
`load_json_history()` tragaba cualquier error con un `except:` sin tipo. Se
acotó a `(json.JSONDecodeError, OSError)` y ahora imprime un aviso a stderr
en vez de fallar en silencio.

## 6. [RESUELTO] `except:` desnudo en `ui/main_ui.py`
Dos casos: `safe_destroy()` (destruir un widget ya destruido) y la carga del
ícono de ventana. Ambos se acotaron a `TclError` (la excepción real que
Tkinter lanza en esos casos) y la del ícono ahora avisa por stderr en vez de
fallar en silencio.

## 7. [RESUELTO] Conexión `pydal` no se cerraba explícitamente
`run_db_scan()` ahora guarda la conexión en una variable y la cierra en un
`finally` (solo si llegó a crearse), tanto si el escaneo tuvo éxito como si
falló.

## 8. `test_syntax.py` no es una suite de tests real
Solo corre `py_compile` sobre los archivos — valida sintaxis, no comportamiento.
Está bien como smoke test, pero no reemplaza tests unitarios (ver BACKLOG.md).

## 9. [RESUELTO] `test_syntax.py` crasheaba por encoding en consolas cp1252
Usaba `✅`/`❌` en los `print()`. En una consola con codepage cp1252 (como
Git Bash/`cmd` en este entorno) eso lanzaba `UnicodeEncodeError` y el script
nunca llegaba a reportar nada. Cambiado a texto plano (`OK`/`ERROR`).

## 10. [RESUELTO] El `.exe` instalado no podía guardar el historial (Permission Denied en Program Files)
`db_manager_app.py` guardaba `db_maps.json` junto al `.exe` real
(`os.path.dirname(sys.executable)`). Cuando el instalador lo pone en
`C:\Program Files\Etch-DB-Mapper\` (la ruta por defecto), Windows bloquea la
escritura ahí sin privilegios de administrador → `PermissionError: [Errno 13]
Permission denied`. Cada escaneo fallaba al intentar guardar, sin importar si
la conexión a la base de datos funcionaba o no. Se movió el historial a
`%LOCALAPPDATA%\Etch-DB-Mapper\db_maps.json` (carpeta de usuario, siempre
escribible), separado de los assets de solo lectura (ícono/logo, que siguen
viniendo del recurso empaquetado). En modo desarrollo (`python
db_manager_app.py`) el comportamiento no cambió: sigue guardando junto al
script.

## 11. [RESUELTO] La URI solo se guardaba si el escaneo tenía éxito
`start_scan_thread()` únicamente escribía en el historial dentro del branch
`if res["status"] == "success"`. Si la conexión fallaba (URI mal escrita,
credenciales incorrectas, driver faltante, etc.), el alias y la URI se
perdían — había que reescribir todo desde cero para reintentar. Se
reestructuró el flujo (`save_history_entry()`) para guardar la conexión
**antes** de intentar escanear (estado `pending`), y actualizarla con
`success` o `error` (+ el mensaje) según el resultado, sin nunca perder la
URI ni los datos de un escaneo exitoso anterior. El historial ahora muestra
✓/⚠ por conexión.

## 12. [RESUELTO] Condición de carrera al editar+reintentar mientras un escaneo viejo seguía en vuelo
Si se editaba la URI y se pedía "Refrescar" mientras el escaneo anterior
(con la URI vieja) todavía no había terminado, el resultado del escaneo
viejo podía llegar *después* y pisar el del nuevo al escribir en
`self.history`. Se agregó un contador de "generación" por alias
(`scan_generation`): cada hilo de escaneo se etiqueta con su generación al
arrancar, y descarta su resultado si para cuando termina ya se inició un
escaneo más nuevo para ese mismo alias.

## 13. [RESUELTO] Los mensajes de error mostraban el traceback completo de Python
`run_db_scan()` devolvía `str(e)` tal cual, y pydal (con psycopg2/pyodbc)
suele incluir el traceback completo dentro del mensaje de la excepción — un
muro de texto ilegible en el banner de notificación de una sola línea. Se
agregó `_summarize_error()`, que se queda con la última línea no vacía (la
excepción real, ej. `psycopg2.OperationalError: ... password authentication
failed`).

## 14. [RESUELTO] Código muerto: `ask_new_scan()`
Método sin ningún caller (ni siquiera como `command=`) en `ui/main_ui.py`,
leftover de una refactorización anterior. Eliminado.

## 15. [RESUELTO] SQL Server fallaba con "0 parameter markers, but 1 parameters were supplied"
Las 3 consultas parametrizadas de `run_db_scan()` usaban `%s` (estilo
"pyformat", el que espera `psycopg2`). `pyodbc` (el driver de SQL Server)
espera `?` (estilo "qmark", PEP 249) — con `%s` literal en el SQL, pyodbc no
reconoce ningún marcador de parámetro y al intentar bindear el valor tira
justo ese error. Como es un error a nivel DBAPI, la conexión y el query de
listado de tablas SÍ funcionaban (por eso `check_driver_available()` no lo
detectaba) — recién fallaba al pedir columnas/FKs/PKs de la primera tabla.
Se agregó `_param_placeholder(uri)`, que elige `?` o `%s` según el motor
detectado. Detectado y corregido probando contra un SQL Server real de
trabajo (171 tablas, 1972 columnas, 199 PK, 44 FK) — nunca se había
verificado de verdad contra SQL Server hasta ahora, pese a que
`docs/BACKLOG.md` decía "ya verificado" (afirmación incorrecta, corregida).
