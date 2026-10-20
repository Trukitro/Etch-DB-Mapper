# Future Plans — Etch-DB-Mapper

Visión a mediano/largo plazo para la versión pública del proyecto.

## Objetivo
App de escritorio publicable, moderna y rápida, que se conecte a cualquier base
accesible por pyDAL, con releases versionados (instalador + `.exe` en GitHub)
y sin ningún dato o configuración ligada al trabajo del autor.

## Ejes de trabajo
1. **Estabilización del core** — ✅ errores explícitos, conexiones cerradas,
   escritura atómica, pruebas automáticas (`tests/`).
2. **Empaquetado** — ✅ `.exe` con PyInstaller + instalador Inno Setup,
   automatizados en `tools/build_windows.ps1`.
3. **Releases públicos** — ✅ `v1.0.0` a `v1.5.0` publicados. La `2.0.0`
   (reescritura a pywebview) está lista y pendiente de publicar
   (`RELEASE_PLAN.md`).
4. **Nueva interfaz** — ✅ 2.0.0: pywebview + HTML/CSS/JS, mapa con
   Cytoscape.js, Ayuda y Novedades dentro de la app
   (`STACK_EXPLORATION.md`, `ARCHITECTURE.md`).
5. **Soporte multi-DB** — ✅ lectores nativos para PostgreSQL, SQL Server,
   MySQL y SQLite; lectura genérica por `INFORMATION_SCHEMA` para el resto.
   Falta: verificar con servidores reales y sumar Oracle/Firebird/DB2.
6. **Linux** — 🗓️ en planificación: `LINUX_PLAN.md`. El código ya es
   multiplataforma; faltan pruebas reales, CI y empaquetado (AppImage / pip).
7. **Comprensión de esquemas sin FKs** — 🗓️ relaciones inferidas por nombre
   de columna para bases antiguas.
8. **Seguridad de credenciales** — 🗓️ guardar las URI cifradas con el
   almacén del sistema (Credential Manager / `keyring`).
9. **Documentación de usuario** — ✅ `HELP.md` y `CHANGELOG.md` en la app;
   falta sumar capturas y GIF al README.

## No-objetivos (por ahora)
- No se van a portar datos, conexiones ni referencias a bases de datos reales
  de ningún entorno de trabajo.
- Edición de datos o ejecución de consultas del usuario: la app es de solo
  lectura de metadatos a propósito.
- macOS: el código no depende de Windows, pero no hay entorno de prueba.
