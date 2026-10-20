# Plan de soporte para Linux

**Estado: en planificación.** Nada de esto está implementado ni probado en Linux todavía. Este documento define qué hay hecho, qué falta y en qué orden conviene hacerlo.

## Punto de partida (ya hecho en 2.0.0)

La reescritura a pywebview dejó el código listo para no depender de Windows:

- `core/paths.py` resuelve la carpeta de datos por sistema operativo (`$XDG_DATA_HOME/Etch-DB-Mapper`, por defecto `~/.local/share/Etch-DB-Mapper`) y acepta `ETCH_DATA_DIR`.
- La interfaz es HTML/CSS/JS local y no usa APIs de Windows. Las fuentes tienen respaldo (`Cantarell`, `Ubuntu`, `DejaVu Sans Mono`…).
- El launcher usa `gui="edgechromium"` solo en Windows; en otros sistemas deja que pywebview elija el motor.
- Los atajos usan `Ctrl` (y aceptan `Cmd`).

## Qué necesita Linux

### 1. Motor web de pywebview
pywebview en Linux necesita un backend: **GTK (WebKit2GTK)** o **Qt (QtWebEngine)**.

| Backend | Paquetes (Debian/Ubuntu) | Notas |
|---|---|---|
| GTK | `python3-gi`, `gir1.2-webkit2-4.1` (o `-4.0`) | Ligero; es el camino recomendado |
| Qt | `pip install pywebview[qt]` | Más pesado (QtWebEngine), mejor aislamiento de versión |

Riesgos a verificar: soporte de `color-mix()` y de las propiedades CSS modernas en la versión de WebKit2GTK de cada distro (la interfaz las usa), `backdrop-filter`, y el rendimiento de Cytoscape en canvas con WebKit. Si WebKit2GTK es muy viejo en alguna distro, el respaldo es el backend Qt.

### 2. Drivers de base de datos

| Motor | Linux |
|---|---|
| PostgreSQL | `psycopg2-binary` funciona sin compilar |
| MySQL / MariaDB | `pymysql` (Python puro) |
| SQLite | incluido |
| SQL Server | `pyodbc` + **unixODBC** (`unixodbc`, `unixodbc-dev`) + driver `msodbcsql18` de Microsoft (repositorio de Microsoft). Dejar documentado `?DRIVER={ODBC Driver 18 for SQL Server}` y `TrustServerCertificate=yes` cuando aplique |

`HELP.md` ya incluye la sección de drivers; falta una subsección específica de SQL Server en Linux.

### 3. Empaquetado

Opciones, de más simple a más completa:

1. **Desde PyPI / `pipx`** (`pip install etch-db-mapper`): requiere publicar el paquete y declarar el backend como extra (`[gtk]`, `[qt]`). Es lo más barato de mantener.
2. **AppImage con PyInstaller**: un archivo ejecutable portable. Hay que empaquetar `webui/`, `HELP.md`, `CHANGELOG.md` (igual que en Windows) y decidir si se incluye el backend Qt (pesado) o se exige GTK del sistema.
3. **Paquete `.deb`** (y quizá `.rpm`/Flatpak): integra menú de aplicaciones e icono (`.desktop` + `favicon`/SVG). Flatpak aislaría el runtime de WebKit.

Recomendación: empezar por (1) y un AppImage con GTK del sistema; evaluar `.deb`/Flatpak si hay demanda.

### 4. Integración de escritorio
- Archivo `.desktop` con icono (`webui/assets/icon.svg` + PNG de 256 px).
- Verificar el diálogo nativo de archivos (`pick_file`, `save_file`) y `webbrowser.open` (`xdg-open`).

### 5. CI
Un workflow de GitHub Actions con matriz `windows-latest` / `ubuntu-latest` que corra `python -m unittest discover -s tests -t .` en ambos. Las pruebas actuales no usan ventana, así que corren sin entorno gráfico. Una etapa posterior puede lanzar la UI con `xvfb-run` para una prueba de humo.

## Hoja de ruta propuesta

| # | Paso | Resultado |
|---|---|---|
| 1 | Correr el código fuente en una VM/WSL con GTK y verificar ventana, mapa y diálogos | Lista de problemas reales de WebKit |
| 2 | Arreglar diferencias de CSS/JS que aparezcan | La UI se ve igual que en Windows |
| 3 | CI con pruebas en Linux | Regresiones detectadas automáticamente |
| 4 | Documentar instalación (GTK + drivers, SQL Server) en `HELP.md` y README | Un usuario nuevo puede instalarlo |
| 5 | Primer artefacto: AppImage o paquete pip | Release `2.x` con binario para Linux |
| 6 | `.deb` / Flatpak (opcional) | Instalación nativa |

## Fuera de alcance por ahora
- macOS (el código no depende de Windows, pero no hay entorno de prueba ni planes de empaquetado).
- Firma de código y repositorios de paquetes propios.
