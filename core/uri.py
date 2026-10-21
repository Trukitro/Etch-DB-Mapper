"""Construir y descomponer URI de pydal para el asistente de conexión.

El asistente (UI) deja al usuario escribir host, puerto, usuario, etc. por
separado y acá se arma la URI. La URI "cruda" sigue siendo una opción: el
usuario avanzado puede escribirla a mano, y `parse_uri` la descompone para
poder mostrarla en el asistente.

Usuario y contraseña se codifican con porcentaje (`@`, `:`, `/`, `%`… no rompen
la URI); `scanner._open_dal` abre pydal con `decode_credentials=True` para
decodificarlos.
"""
import re
from urllib.parse import quote, unquote

# motor -> esquema que se escribe por defecto, puerto por defecto, etiqueta
ENGINES = {
    "postgres": {"label": "PostgreSQL", "scheme": "postgres", "port": 5432},
    "mssql": {"label": "SQL Server", "scheme": "mssql4", "port": 1433},
    "mysql": {"label": "MySQL / MariaDB", "scheme": "mysql", "port": 3306},
    "sqlite": {"label": "SQLite", "scheme": "sqlite", "port": None},
}

_SCHEME_ENGINE = (("postgres", "postgres"), ("mssql", "mssql"), ("mysql", "mysql"), ("sqlite", "sqlite"))


_MASK_RE = re.compile(r"^([a-zA-Z0-9:+]+://)([^:/@]+):(.*)@")


def mask_uri(uri: str) -> str:
    """Oculta la contraseña para mostrarla en pantalla o en logs."""
    return _MASK_RE.sub(lambda m: m.group(1) + m.group(2) + ":" + "••••" + "@", uri or "", count=1)


def has_password(uri: str) -> bool:
    return bool(_MASK_RE.match(uri or ""))


def engine_of_scheme(scheme: str):
    s = (scheme or "").lower()
    for prefix, engine in _SCHEME_ENGINE:
        if s.startswith(prefix):
            return engine
    return None


def _clean(value) -> str:
    return str(value if value is not None else "").strip()


def build_uri(fields: dict) -> str:
    """Arma la URI a partir de los campos del asistente.

    Campos: engine, host, port, user, password, database, driver, trust_cert,
    path (sqlite), scheme (opcional, conserva variantes como mssql4n), extra
    (argumentos de URI adicionales, ya con formato k=v&k=v).
    Lanza ValueError con un mensaje en español si falta algo.
    """
    engine = _clean(fields.get("engine"))
    if engine not in ENGINES:
        raise ValueError("Elegí un tipo de base de datos.")
    scheme = _clean(fields.get("scheme"))
    if not scheme or engine_of_scheme(scheme) != engine:
        scheme = ENGINES[engine]["scheme"]

    if engine == "sqlite":
        path = _clean(fields.get("path")).replace("\\", "/")
        if not path:
            raise ValueError("Indicá la ruta del archivo SQLite.")
        return f"{scheme}://{path}"

    host, user, db = _clean(fields.get("host")), _clean(fields.get("user")), _clean(fields.get("database"))
    if not host:
        raise ValueError("Falta el servidor (host o IP).")
    if re.search(r"[\s/@?#]", host):
        raise ValueError("El servidor no puede tener espacios ni los caracteres / @ ? #.")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"          # IPv6
    if not user:
        raise ValueError("Falta el usuario.")
    if not db:
        raise ValueError("Falta el nombre de la base de datos.")
    if re.search(r"[?#]", db):
        raise ValueError("El nombre de la base no puede llevar ? ni #.")

    port = _clean(fields.get("port"))
    if port:
        if not port.isdigit() or not 0 < int(port) < 65536:
            raise ValueError("El puerto debe ser un número entre 1 y 65535.")
        port = f":{int(port)}"

    password = fields.get("password") or ""
    cred = quote(user, safe="") + (":" + quote(password, safe="") if password else "")

    args = []
    if engine == "mssql":
        driver = _clean(fields.get("driver"))
        if driver:
            args.append("DRIVER={" + driver.strip("{}") + "}")
        if fields.get("trust_cert"):
            args.append("TrustServerCertificate=yes")
    extra = _clean(fields.get("extra")).lstrip("?&")
    if extra:
        args.append(extra)
    query = "?" + "&".join(args) if args else ""
    return f"{scheme}://{cred}@{host}{port}/{db}{query}"


def parse_uri(uri: str):
    """URI -> campos del asistente, o None si no se puede descomponer
    (motor desconocido, DSN de SQL Server sin '@', etc.)."""
    uri = _clean(uri)
    if "://" not in uri:
        return None
    scheme, rest = uri.split("://", 1)
    engine = engine_of_scheme(scheme)
    if engine is None:
        return None
    base = {"engine": engine, "scheme": scheme}
    if engine == "sqlite":
        return {**base, "path": rest}
    if "@" not in rest:
        return None
    userinfo, _, location = rest.rpartition("@")     # el último '@': tolera claves con '@' sin codificar
    user, _, password = userinfo.partition(":")
    m = re.match(r"^(?P<host>\[[^\]]+\]|[^:/]*)(?::(?P<port>\d+))?/(?P<db>[^?]*)(?:\?(?P<args>.*))?$", location)
    if not m or not user:
        return None
    host = m.group("host")
    if host.startswith("["):
        host = host[1:-1]
    fields = {**base, "host": host, "port": m.group("port") or "", "user": unquote(user), "password": unquote(password),
              "database": m.group("db"), "driver": "", "trust_cert": False, "extra": ""}
    rest_args = []
    for part in (m.group("args") or "").split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        if engine == "mssql" and key.upper() == "DRIVER":
            fields["driver"] = value.strip("{}")
        elif engine == "mssql" and key.lower() == "trustservercertificate":
            fields["trust_cert"] = value.lower() in ("yes", "true", "1")
        else:
            rest_args.append(part)
    fields["extra"] = "&".join(rest_args)
    return fields


def target_of(uri: str):
    """(host, puerto) de una URI de red, o None (sqlite, DSN, no reconocida)."""
    f = parse_uri(uri)
    if not f or f["engine"] == "sqlite" or not f["host"]:
        return None
    port = int(f["port"]) if f["port"] else ENGINES[f["engine"]]["port"]
    return f["host"], port


def odbc_drivers():
    """Drivers ODBC de SQL Server instalados, del más nuevo al más viejo."""
    try:
        import pyodbc
        found = [d for d in pyodbc.drivers() if "sql server" in d.lower()]
    except Exception:
        return []

    def rank(name):
        m = re.search(r"ODBC Driver (\d+)", name)
        return (0, -int(m.group(1))) if m else (1, 0)

    return sorted(found, key=rank)
