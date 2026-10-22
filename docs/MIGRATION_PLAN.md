# Plan de migración entre motores

Objetivo: migrar bases de datos de un motor a otro (SQL Server ⇄ PostgreSQL ⇄ MySQL ⇄ SQLite) con la **base de origen en solo lectura** y un **destino nuevo o vacío**, evitando conflictos y sorpresas. Se hace por fases, de menor a mayor riesgo.

| Fase | Qué hace | Estado | Riesgo |
|---|---|---|---|
| **1. Solo esquema** | Genera el script `CREATE TABLE` para el motor destino. No se conecta al destino. | ✅ 2.4.0 | Ninguno |
| **2. Copiar datos** | Copia los datos al destino vacío, con plan, simulacro y verificación. | ✅ 2.5.0 | Medio, mitigado por las reglas de abajo |
| **3. Casos difíciles** | Reanudar, tablas enormes, ciclos de claves, BLOB, zonas horarias… | 🗓️ Idea | Alto |

## Fase 1 (hecha): script de esquema

`core/migrate.py` toma el esquema escaneado y produce el SQL del destino. Pestaña **Migrar** de la app; API `plan_migration(alias, destino, opciones)`.

**Qué traduce:** tablas, columnas y tipos (mapa de tipos entre motores), nulabilidad, clave primaria (simple y compuesta), claves foráneas (compuestas incluidas), restricciones UNIQUE, identidad/autoincremento, valores por defecto conocidos, y descripciones (las de la base y las notas del usuario).

**Lo que garantiza el script:**
- Solo sentencias que **crean** objetos nuevos. Sin `DROP`, `TRUNCATE`, `DELETE`, `UPDATE`, `INSERT` ni `IF NOT EXISTS` (si algo ya existe, falla en vez de pisarlo). Hay una prueba automática que lo comprueba para cada motor.
- Las claves foráneas van al final (`ALTER TABLE … ADD CONSTRAINT`), así el orden de creación nunca falla por ciclos; en SQLite van dentro de `CREATE TABLE`.
- Opciones para aislar lo migrado: **esquema nuevo** (PostgreSQL/SQL Server), **prefijo** de tablas y estilo de nombres.

**Lo que no hace (y lo avisa en el informe):** índices no únicos, `CHECK`, reglas `ON DELETE/ON UPDATE`, vistas, procedimientos, triggers y los datos. Todo valor por defecto o tipo que no sabe traducir se omite con una advertencia; **nunca adivina**.

**Casos delicados que ya maneja:**
- `timestamp` de SQL Server es un contador binario (`rowversion`), no una fecha.
- Columnas de texto usadas como clave: SQL Server y MySQL no aceptan `MAX`/`TEXT` en una clave, así que se acotan (y las claves foráneas heredan el mismo tipo que el padre).
- PostgreSQL/MySQL/SQLite guardan Unicode: hacia SQL Server se usa `NVARCHAR` para no perder caracteres.
- Nombres demasiado largos y colisiones de nombres se marcan como **error**.

**Verificación:** el script de **SQLite** se ejecuta de verdad en las pruebas (incluida una ida y vuelta SQLite → SQLite comparando tablas, columnas, claves y UNIQUE). La sintaxis de PostgreSQL, SQL Server y MySQL está cubierta por pruebas de texto y revisada, pero **no se ha ejecutado contra servidores reales**: prueba el script primero en una base desechable.

## Fase 2 (hecha en 2.5.0): copiar los datos

Implementada en `core/copy_engine.py` y en *Migrar → Copiar datos*. Todas las reglas de seguridad de abajo se cumplen y tienen prueba automática (origen intacto byte a byte, destino no vacío o con colisión bloqueado, confirmación exacta, destino que cambia tras la revisión, cancelación, fallo a mitad de tabla). **Verificación real:** SQLite → SQLite de punta a punta, y lectura de un PostgreSQL real hacia un SQLite temporal con los conteos iguales. **Sin verificar contra servidores reales:** la *escritura* en PostgreSQL, SQL Server y MySQL y la lectura de SQL Server/MySQL (se prueban con un destino falso que registra las sentencias). Diferencias respecto del diseño original: no hay verificación por suma de control (solo conteos de filas) ni reanudación; el origen de SQL Server se protege con una guardia de la app porque no existe un modo de sesión de solo lectura.

### Diseño original

### Reglas de seguridad (innegociables)

1. **El origen es solo lectura, y lo impone la base, no solo la app.** La conexión de origen se abre en una transacción de solo lectura: `SET TRANSACTION READ ONLY` (PostgreSQL), `START TRANSACTION READ ONLY` (MySQL), `ApplicationIntent=ReadOnly` (SQL Server). Si algo intentara escribir, la base lo rechaza.
2. **El destino debe estar limpio.** Antes de escribir se comprueba que no tenga tablas de usuario (o, con esquema/prefijo nuevo, que no exista nada con esos nombres). Si hay conflicto, **se niega** y explica por qué.
3. **Nunca sobrescribir ni borrar.** Sin `DROP`, `TRUNCATE`, `DELETE` ni `UPDATE` sobre lo existente.
4. **Plan antes de ejecutar:** qué se creará, cuántas filas, cuánto tardará aproximadamente. Confirmación escribiendo el nombre del destino.
5. **Simulacro** (dry run): traduce y valida todo sin escribir nada.
6. **Todo o nada por tabla** (transacción) y un **informe final**.
7. **Verificación al terminar:** conteo de filas por tabla y suma de control de columnas clave; las diferencias se muestran, no se ocultan.
8. Las credenciales del destino se tratan igual que las del origen: cifradas, nunca en registros.

### Diseño técnico

- Orden de copia por dependencias de claves foráneas (padres primero); ciclos con restricciones diferidas o carga en dos pasadas.
- Lectura por lotes (cursor) y escritura por lotes (`executemany` / `COPY` en PostgreSQL / `BULK INSERT` donde aplique) con progreso por tabla y cancelación.
- Identidades: insertar valores explícitos (`SET IDENTITY_INSERT ON`, `OVERRIDING SYSTEM VALUE`, etc.) y luego ajustar la secuencia al máximo.
- Conversión de valores en Python con las mismas reglas del mapa de tipos (booleanos, fechas con zona, `Decimal`, binarios).
- Cada fila que falle la conversión se registra en un informe de rechazos en lugar de detener todo en silencio.

### Cambios de promesa que hay que documentar al llegar a esta fase

Hoy la app dice «solo lee metadatos». La fase 2 lee datos y escribe en el destino: irá en una sección separada, con consentimiento explícito, y se actualizarán `SECURITY.md` y la ayuda.

## Fase 3 (idea)

Reanudar una copia interrumpida, tablas muy grandes, columnas BLOB, zonas horarias y colaciones, informe de compatibilidad de vistas/procedimientos/triggers («revisar a mano») y mapa de tipos editable por el usuario.
