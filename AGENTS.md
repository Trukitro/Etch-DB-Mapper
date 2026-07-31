# AGENTS.md

## Proyecto
Etch-DB-Mapper es una app Python de escritorio para mapear esquemas de bases
de datos relacionales (probado contra SQL Server y Postgres vía `pydal`).
Usa:
- customtkinter para UI
- tkinter Canvas para mapas
- pydal para conexión a la base de datos
- JSON local para historial

## Estructura
- db_manager_app.py: launcher principal
- core/scanner.py: conexión a la BD y extracción de metadata (INFORMATION_SCHEMA,
  agnóstico de motor)
- core/storage.py: lectura/escritura JSON
- ui/main_ui.py: interfaz principal y canvas

## Reglas para Codex
- Mantener arquitectura modular: lógica de DB en core/, UI en ui/.
- No mover lógica pesada al archivo db_manager_app.py.
- No romper compatibilidad con CustomTkinter.
- No hardcodear credenciales ni URIs.
- Validar cambios con:
  python -m py_compile db_manager_app.py core/scanner.py core/storage.py ui/main_ui.py
- Antes de cambiar scanner.py, revisar seguridad SQL y evitar concatenar nombres sin validación.
- Para errores de UI, mantener operaciones largas en threading y actualizar widgets con self.after().
- Documentar cambios importantes en README.md y docs/.
- Este es el repo público (Etch-DB-Mapper). No incluir datos, credenciales ni referencias
  de ningún cliente o entorno de trabajo real — solo datos de prueba genéricos.
- El autor prueba manualmente contra una base Postgres local propia y,
  puntualmente, contra un SQL Server real de su trabajo (para diagnosticar
  bugs específicos de motor) — ninguna de las dos URIs vive en este repo ni
  se versiona nunca. Si el autor comparte una URI real en el chat para
  diagnóstico, usarla solo en memoria (nunca escribirla a un archivo del
  proyecto, ni a `db_maps.json`/`%LOCALAPPDATA%`, ni a un commit) y no
  pedirla ni asumirla en el código — el scanner debe seguir funcionando por
  URI arbitraria que el usuario ingrese.

## Estilo
- Código claro, simple y compatible con Windows.
- Mensajes de UI en español.
- Evitar dependencias nuevas salvo que sean necesarias.
