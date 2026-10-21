"""Cifrado de las contraseñas guardadas.

En Windows se usa DPAPI (la API de protección de datos del sistema, vía
ctypes: sin dependencias nuevas). Lo que se guarda en disco solo lo puede
descifrar **el mismo usuario de Windows en el mismo equipo**; copiar
`db_maps.json` a otra PC o cuenta no revela la contraseña.

En otros sistemas todavía no hay un almacén integrado (ver docs/LINUX_PLAN.md):
`get_protector()` devuelve un protector "no disponible" y la UI lo informa con
claridad en lugar de aparentar una seguridad que no existe.
"""
import base64
import sys

PREFIX = "dpapi:v1:"
_ENTROPY = b"Etch-DB-Mapper/credentials/v1"   # sal propia de la app (no es un secreto)


class SecretError(Exception):
    """No se pudo cifrar o descifrar (otro usuario/equipo, dato dañado…)."""


class NullProtector:
    name = "none"
    available = False
    label = "No disponible en este sistema: las contraseñas se guardan sin cifrar."

    def protect(self, text: str) -> str:
        raise SecretError("Cifrado no disponible")

    def unprotect(self, token: str) -> str:
        raise SecretError("Cifrado no disponible")


class WindowsProtector:
    name = "dpapi"
    available = True
    label = "Cifradas con Windows (DPAPI), ligadas a tu usuario y a este equipo."

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        self._ctypes, self._Blob = ctypes, Blob
        crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
        for fn in (crypt32.CryptProtectData, crypt32.CryptUnprotectData):
            fn.restype = wintypes.BOOL
        crypt32.CryptProtectData.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p,
                                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p,
                                               ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._crypt32, self._kernel32 = crypt32, kernel32

    def _blob(self, data: bytes):
        buf = self._ctypes.create_string_buffer(data, len(data))
        return self._Blob(len(data), self._ctypes.cast(buf, self._ctypes.POINTER(self._ctypes.c_char))), buf

    def _run(self, fn, data: bytes, protect: bool) -> bytes:
        ct = self._ctypes
        src, keep1 = self._blob(data)
        ent, keep2 = self._blob(_ENTROPY)
        out = self._Blob()
        UI_FORBIDDEN = 0x1
        if protect:
            ok = fn(ct.byref(src), "Etch-DB-Mapper", ct.byref(ent), None, None, UI_FORBIDDEN, ct.byref(out))
        else:
            ok = fn(ct.byref(src), None, ct.byref(ent), None, None, UI_FORBIDDEN, ct.byref(out))
        if not ok:
            raise SecretError("Windows no pudo procesar el dato (¿otro usuario o equipo?)")
        try:
            return ct.string_at(out.pbData, out.cbData)
        finally:
            self._kernel32.LocalFree(out.pbData)
            del keep1, keep2

    def protect(self, text: str) -> str:
        raw = self._run(self._crypt32.CryptProtectData, text.encode("utf-8"), True)
        return PREFIX + base64.b64encode(raw).decode("ascii")

    def unprotect(self, token: str) -> str:
        if not token.startswith(PREFIX):
            raise SecretError("Formato de dato cifrado desconocido")
        try:
            raw = base64.b64decode(token[len(PREFIX):])
        except ValueError as e:
            raise SecretError("Dato cifrado dañado") from e
        return self._run(self._crypt32.CryptUnprotectData, raw, False).decode("utf-8")


def get_protector():
    """Mejor protector disponible; nunca lanza."""
    if sys.platform == "win32":
        try:
            p = WindowsProtector()
            if p.unprotect(p.protect("etch-selftest")) == "etch-selftest":
                return p
        except Exception:
            pass
    return NullProtector()
