import re
import time
import importlib.util
from datetime import datetime
from pydal import DAL

# Prefijo de URI (pydal) -> (módulo Python requerido, cómo instalarlo).
# módulo None = no requiere driver externo (ej: sqlite, stdlib).
DRIVER_HINTS = {
    "mssql": ("pyodbc", "pip install pyodbc"),
    "postgres": ("psycopg2", "pip install psycopg2-binary"),
    "mysql": ("pymysql", "pip install pymysql"),
    "sqlite": (None, None),
    "oracle": ("cx_Oracle", "pip install cx_Oracle"),
    "firebird": ("fdb", "pip install fdb"),
    "db2": ("ibm_db", "pip install ibm_db"),
    "mongodb": ("pymongo", "pip install pymongo"),
}

# Cada driver DBAPI tiene su propio "paramstyle" (PEP 249) para marcadores de
# parámetro en executesql(). psycopg2/pymysql usan %s (pyformat); pyodbc y
# sqlite3 usan ? (qmark). Usar el que no corresponde no rompe en la conexión
# ni en el parseo - el motor literalmente cuenta 0 marcadores reconocidos y
# tira "0 parameter markers, but 1 parameters were supplied" al ejecutar.
QMARK_ENGINES = {"mssql", "sqlite", "firebird", "db2"}


def _param_placeholder(uri):
    """Marcador de parámetro correcto para executesql() según el motor de
    la URI. Default '%s' (pyformat) para motores no reconocidos - es el
    driver más común (psycopg2/pymysql)."""
    engine = detect_engine(uri)
    return "?" if engine in QMARK_ENGINES else "%s"


def _summarize_error(exc):
    """pydal (y algunos drivers como psycopg2/pyodbc) devuelven excepciones
    cuyo str() es un traceback completo, no un mensaje legible. Nos quedamos
    con la última línea no vacía, que suele ser la excepción real (ej:
    "psycopg2.OperationalError: ... password authentication failed")."""
    msg = str(exc).strip()
    for line in reversed(msg.splitlines()):
        if line.strip():
            return line.strip()
    return msg or exc.__class__.__name__


def detect_engine(uri):
    """Extrae el motor a partir del prefijo de una URI pydal (ej: 'mssql4://...' -> 'mssql')."""
    match = re.match(r"^([a-zA-Z0-9]+)", uri or "")
    if not match:
        return None
    prefix = match.group(1).lower()
    for engine in DRIVER_HINTS:
        if prefix.startswith(engine):
            return engine
    return None


def check_driver_available(uri):
    """Si la URI requiere un driver Python que no está instalado, retorna un
    mensaje de error claro. Si todo está bien (o el motor no se reconoce),
    retorna None."""
    engine = detect_engine(uri)
    if not engine:
        return None
    module_name, install_hint = DRIVER_HINTS[engine]
    if module_name is None:
        return None
    if importlib.util.find_spec(module_name) is None:
        return (
            f"Falta el driver '{module_name}' para conectar a {engine}. "
            f"Instalalo con: {install_hint}"
        )
    return None


def run_db_scan(uri):
    """Realiza el escaneo de la base de datos y retorna el mapa de tablas."""
    start_t = time.time()

    driver_error = check_driver_available(uri)
    if driver_error:
        return {"status": "error", "message": driver_error}

    db = None
    try:
        db = DAL(uri, migrate_enabled=False, folder=None)
        ph = _param_placeholder(uri)
        # Consulta para obtener nombres de tablas. Se excluyen los esquemas de
        # sistema en vez de fijar 'dbo' (SQL Server) para que también funcione
        # contra Postgres ('public'), MySQL, etc.
        tables = db.executesql("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA NOT IN ('information_schema', 'pg_catalog', 'sys')""")
        full_map = {}

        for t in [x[0] for x in tables]:
            # Obtener columnas
            cols = db.executesql(f"SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = {ph}", (t,))
            # Obtener Foreign Keys
            fks = db.executesql(f"""
                SELECT kcu.COLUMN_NAME, rel_kcu.TABLE_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE rel_kcu ON rc.UNIQUE_CONSTRAINT_NAME = rel_kcu.CONSTRAINT_NAME
                WHERE kcu.TABLE_NAME = {ph}""", (t,))
            # Obtener columnas de la Primary Key
            pks = db.executesql(f"""
                SELECT ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME AND tc.TABLE_NAME = ku.TABLE_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND tc.TABLE_NAME = {ph}""", (t,))
            pk_names = {p[0] for p in pks}

            full_map[t] = {
                "columns": [{"name": c[0], "type": c[1], "null": c[2], "is_pk": c[0] in pk_names} for c in cols],
                "relations": [{"col": f[0], "ref_table": f[1]} for f in fks]
            }

        duration = round(time.time() - start_t, 2)
        return {
            "data": full_map,
            "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": duration,
            "status": "success"
        }
    except Exception as e:
        return {"status": "error", "message": _summarize_error(e)}
    finally:
        if db is not None:
            db.close()
