# Release Plan — Etch-DB-Mapper

Cómo se publica este proyecto, siguiendo el mismo patrón que las demás apps de
la línea "Etch". Nada de esto se ejecuta automáticamente: cada paso con impacto
externo (push, tag, release en GitHub) se confirma con el autor antes.

## 1. Preparar la versión
- Actualizar la versión en `core/version.py` (única fuente: la usan la app, el
  instalador y el nombre de los artefactos).
- Agregar la entrada en `CHANGELOG.md` (formato Keep a Changelog). Es lo que
  ven los usuarios en **Novedades** dentro de la app.
- Revisar `HELP.md` si cambió algún flujo.
- Mover lo hecho en `docs/BACKLOG.md`.

## 2. Compilar
```powershell
.\tools\build_windows.ps1 -Installer
```
Hace, en orden: comprobación de sintaxis → `python -m unittest` →
`.exe` con PyInstaller en `dist\Etch-DB-Mapper.exe` → instalador con Inno Setup
en `installer\output\Etch-DB-Mapper-Setup-vX.Y.Z.exe`.

Requisitos en la máquina de build: Python 3.10+, `pip install -r requirements.txt pyinstaller`,
Inno Setup 6.

## 3. Verificar
- Abrir `dist\Etch-DB-Mapper.exe` (idealmente en una máquina sin Python): debe
  verse la pantalla de inicio y funcionar «Probar con una base de ejemplo».
- Probar instalar y desinstalar con el instalador.
- Confirmar que no hay datos de prueba, `db_maps*.json` ni credenciales dentro
  del `.exe` o del instalador.

## 4. Publicar (con confirmación del autor)
```bash
git push origin main
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z dist/Etch-DB-Mapper.exe installer/output/Etch-DB-Mapper-Setup-vX.Y.Z.exe \
   --title "vX.Y.Z" --notes-file <notas>
```
Las notas salen de la entrada correspondiente de `CHANGELOG.md`.

## Requisito de ejecución
La app necesita el runtime **Microsoft Edge WebView2** (incluido en Windows 11
y en Windows 10 actualizado). El instalador avisa si no lo detecta.
