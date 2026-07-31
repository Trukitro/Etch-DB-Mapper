# Future Plans — Etch-DB-Mapper

Visión a mediano/largo plazo para la versión pública del proyecto.

## Objetivo
Llevar Etch-DB-Mapper de "herramienta interna" a app de escritorio publicable,
con releases versionados (.exe + instalador) en GitHub, sin ningún dato o
config ligada al trabajo del autor.

## Ejes de trabajo
1. **Estabilización del core** — limpiar manejo de errores, cerrar conexiones
   `pydal` correctamente, cubrir `scanner.py`/`storage.py` con pruebas básicas.
2. **Empaquetado** — generar `.exe` con PyInstaller y un instalador tipo wizard
   (Inno Setup u otro), siguiendo el mismo patrón que las demás apps "Etch".
3. **Primer release público** — ✅ hecho, tag `v1.0.0` en
   https://github.com/Trukitro/Etch-DB-Mapper/releases/tag/v1.0.0 con el .exe
   y el instalador como assets.
4. **Motores de mapa adicionales** — evaluar cuáles de los layouts explorados
   en versiones anteriores (radial, jerárquico, zonificado, tráfico, neural)
   vale la pena mantener como opciones oficiales en la UI, y cuáles fueron
   solo experimentos.
5. **Soporte multi-DB** — ✅ el query de esquema ya no está atado a `'dbo'`
   (SQL Server), hay detección de driver faltante con mensaje claro, y el
   estilo de parámetro (`?` vs `%s`) se elige según el motor. Verificado de
   verdad contra Postgres y SQL Server reales (`BUGS.md` #15). Falta:
   probar MySQL.
6. **Documentación de usuario** — screenshots, GIF de uso, guía rápida en el
   README para gente que no conoce el proyecto.

## No-objetivos (por ahora)
- No se van a portar datos, conexiones ni referencias a bases de datos reales
  de ningún entorno de trabajo.
- No se prioriza compatibilidad con Linux/Mac mientras el foco sea Windows
  (.exe + instalador).
