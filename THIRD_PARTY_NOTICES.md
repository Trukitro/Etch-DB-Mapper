# Avisos de terceros

Etch-DB-Mapper incluye (vendorizados en `webui/vendor/`, sin CDN, para funcionar sin internet) los siguientes componentes de código abierto, todos bajo licencia MIT. Cada licencia completa está junto al archivo (`LICENSE.*.txt`).

| Componente | Versión | Archivo | SHA-256 |
|---|---|---|---|
| [Cytoscape.js](https://js.cytoscape.org/) | 3.34.4 | `cytoscape.min.js` | `081591ab735b2b6a3b31a3c60f8f3a3e2fee8c92939e0c7820ad1208571b6cd8` |
| [cytoscape-fcose](https://github.com/iVis-at-Bilkent/cytoscape.js-fcose) | — | `cytoscape-fcose.js` | `4b1cab218d74996aa59cd8473f9239cc6398b8c1774d84d7e59ad9a68959cb57` |
| [cose-base](https://github.com/iVis-at-Bilkent/cose-base) | — | `cose-base.js` | `7cae9509bd36235a63a85e71c8d9fa2cd0bc1d0c1ecc5b5a737976f39d040ddf` |
| [layout-base](https://github.com/iVis-at-Bilkent/layout-base) | — | `layout-base.js` | `ec15ab5df9af3f20708f4faab994accf91cda71848cd5bb10a23432cc50b6745` |

Los hashes permiten comprobar que los archivos no fueron alterados respecto de los publicados por sus autores.

## Dependencias de Python (no incluidas en el repositorio)

| Paquete | Uso | Licencia |
|---|---|---|
| [pywebview](https://pywebview.flowrl.com/) | Ventana nativa con motor web | BSD-3-Clause |
| [pyDAL](https://github.com/web2py/pydal) | Capa de acceso a bases de datos | BSD-3-Clause |
| psycopg2-binary / pyodbc / pymysql | Drivers opcionales de PostgreSQL, SQL Server y MySQL | LGPL / MIT / MIT |

El ejecutable de Windows (PyInstaller) empaqueta estas dependencias junto con el intérprete de Python; consultá sus licencias para los términos de redistribución.
