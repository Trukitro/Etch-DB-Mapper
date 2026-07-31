# Release Plan — Etch-DB-Mapper

Cómo se piensa publicar este proyecto, siguiendo el mismo patrón que las demás
apps de la línea "Etch" del autor. Nada de esto se ejecuta automáticamente —
cada paso con impacto externo (push, release en GitHub) se confirma antes de
hacerse.

## 1. Preparar el repo local
- `git init` en este folder.
- `git remote add origin https://github.com/Trukitro/Etch-DB-Mapper.git`.
- Primer commit con el código base + docs.

## 2. Build del ejecutable
- Empaquetar con PyInstaller:
  `pyinstaller --noconfirm --onefile --windowed --icon favicon.ico db_manager_app.py`
- Verificar que el `.exe` corre standalone (sin Python instalado) en una
  máquina limpia o VM.

## 3. Instalador wizard
- Generar instalador con Inno Setup (u otra herramienta wizard que se use en
  las demás apps Etch), apuntando al `.exe` generado en el paso 2.
- Icono y metadata del instalador consistentes con el resto de la línea Etch.

## 4. Release en GitHub
- Tag de versión (ej. `v1.0.0`).
- `gh release create` (o vía UI) en
  https://github.com/Trukitro/Etch-DB-Mapper con:
  - El `.exe` standalone.
  - El instalador wizard.
  - Notas de release basadas en `BACKLOG.md` (qué se resolvió) y
    `FUTURE_PLANS.md` (qué sigue).

## Antes de publicar
- Confirmar que no queden datos de prueba, `db_maps*.json`, ni nada del
  entorno de trabajo empaquetado en el `.exe` o el instalador.
- Confirmar explícitamente con el autor antes de cualquier `git push` o
  `gh release create` — son acciones visibles públicamente.
