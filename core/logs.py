"""Registro (etch.log) que nunca guarda contraseñas.

`SecretScrubFilter` limpia el mensaje y también el traceback (los drivers a veces
repiten la cadena de conexión dentro de la excepción) antes de escribirlos.
"""
import logging
import traceback

from .scanner import scrub_secrets


class SecretScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = scrub_secrets(record.getMessage())
            record.args = ()
            if record.exc_info:
                record.exc_text = scrub_secrets("".join(traceback.format_exception(*record.exc_info)))
                record.exc_info = None
        except Exception:   # un fallo del filtro no debe perder el mensaje de log
            pass
        return True
