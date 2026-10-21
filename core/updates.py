"""Aviso de versión nueva.

Hace UNA petición GET a la API pública de releases de GitHub
(api.github.com/repos/Trukitro/Etch-DB-Mapper/releases/latest). No envía datos
tuyos ni de tus bases: solo viaja lo que cualquier petición HTTP lleva (tu IP y
el User-Agent "Etch-DB-Mapper/<versión>"). Se hace como máximo una vez al día,
se puede apagar en Preferencias o con la variable de entorno
ETCH_NO_UPDATE_CHECK=1, y nunca descarga ni instala nada: solo avisa y abre la
página del release en tu navegador.
"""
import json
import os
import re
import urllib.request

from .version import APP_NAME, REPO_URL, __version__

API_URL = "https://api.github.com/repos/Trukitro/Etch-DB-Mapper/releases/latest"
TRUSTED_PREFIX = REPO_URL.rstrip("/") + "/"


def parse_version(text: str):
    """'v2.1.1' -> (2, 1, 1); None si no se entiende."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def disabled_by_env() -> bool:
    return os.environ.get("ETCH_NO_UPDATE_CHECK", "").strip() not in ("", "0")


def _fetch(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{__version__}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 (URL fija, https)
        return json.loads(resp.read().decode("utf-8"))


def check_latest(current: str = __version__, fetch=_fetch, timeout: float = 6.0) -> dict:
    """{"ok": True, "current", "latest", "newer": bool, "url"} o {"ok": False, "error"}."""
    try:
        data = fetch(API_URL, timeout)
    except Exception as e:   # sin internet, límite de la API, etc.: no es un error de la app
        return {"ok": False, "error": f"No se pudo consultar GitHub ({e.__class__.__name__})."}
    latest = parse_version(data.get("tag_name"))
    cur = parse_version(current)
    if latest is None or cur is None:
        return {"ok": False, "error": "Respuesta de GitHub no reconocida."}
    url = data.get("html_url") or ""
    if not url.startswith(TRUSTED_PREFIX):
        url = TRUSTED_PREFIX + "releases/latest"
    return {"ok": True, "current": current, "latest": ".".join(map(str, latest)), "newer": latest > cur, "url": url}
