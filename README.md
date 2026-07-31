# Etch-DB-Mapper

**Etch-DB-Mapper** es una herramienta de escritorio para mapear esquemas de bases de
datos relacionales (probado con SQL Server y Postgres), visualizar relaciones entre
tablas mediante distintos algoritmos de layout ("urbanismo de datos") y facilitar la
exploración de bases de datos densas.

Repo: https://github.com/Trukitro/Etch-DB-Mapper

## 🚀 Arquitectura del Proyecto
El proyecto sigue un patrón modular que separa la lógica de negocio de la interfaz visual:

- **`core/`**: El "cerebro" de la aplicación.
  - `scanner.py`: Conexión a la base de datos mediante `pydal` (SQL Server, Postgres...)
    y extracción de metadatos vía `INFORMATION_SCHEMA`.
  - `storage.py`: Persistencia de datos en JSON y utilidades de formateo.
- **`ui/`**: La capa visual (Frontend).
  - `main_ui.py`: Interfaz principal construida con `CustomTkinter`.
- **`db_manager_app.py`**: Punto de entrada principal (Launcher).

## 🛠️ Características Principales
- **Motor de Relaciones Puras**: Filtrado automático de tablas huérfanas para limpiar el mapa.
- **Zonificación Dinámica**: Segregación de tablas sin relación en una vista dedicada.
- **Mapa interactivo**: arrastrá las tablas a mano (drag & drop) y las conexiones
  se actualizan en vivo; la posición de cada una se guarda y persiste entre sesiones.
  "🔄 Auto-Organizar" para volver a la distribución automática cuando quieras.
- **Focus Mode**: pasar el mouse sobre una tabla o conexión resalta solo sus
  relaciones activas y atenúa el resto.
- **Badges de esquema**: 🔑 Primary Key y 🔗 Foreign Key visibles directamente
  en cada columna, tanto en el mapa como en el Explorador.
- **Explorador con dashboard**: tarjetas de tabla, resumen rápido (tablas,
  columnas, relaciones, huérfanas), búsqueda por tabla o columna, y
  "📋 Copiar DDL" para llevarte un `CREATE TABLE` aproximado al portapapeles.
- **Tema claro/oscuro**: toggle 🌙/☀️ en la barra lateral.

## 📦 Instalación
1. Clonar el repositorio.
2. Instalar dependencias: `pip install customtkinter pydal`.
3. Instalar el driver del motor que vayas a usar: `psycopg2` para Postgres,
   `pyodbc` para SQL Server, etc.
4. Ejecutar: `python db_manager_app.py`.

## 📚 Documentación
Ver [`docs/`](docs/) para roadmap, backlog y bugs conocidos.

## Estado
Proyecto público/portfolio, independiente de cualquier entorno de trabajo. No incluye
credenciales, URIs ni datos reales de ningún cliente — solo datos de prueba locales
que no se publican.
