"""Configuración de logs. Los parámetros ``token`` y ``firma`` nunca se escriben (especificación 9, decisión T11)."""

from __future__ import annotations

import logging
import re

_PATRON_SECRETOS = re.compile(r"((?:^|[?&])(?:token|firma)=)[^&\s\"]+", re.IGNORECASE)


def ocultar_secretos(texto: str) -> str:
    return _PATRON_SECRETOS.sub(r"\1***", texto)


class FiltroSecretos(logging.Filter):
    """Reemplaza el valor de ``token=`` y ``firma=`` en los mensajes y argumentos del log."""

    def filter(self, registro: logging.LogRecord) -> bool:
        if isinstance(registro.msg, str):
            registro.msg = ocultar_secretos(registro.msg)
        if isinstance(registro.args, tuple):
            registro.args = tuple(ocultar_secretos(a) if isinstance(a, str) else a for a in registro.args)
        return True


def configurar_registro(nivel: str = "INFO") -> None:
    logging.basicConfig(
        level=nivel.upper(),
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # APScheduler anuncia cada ejecución (cada 5 s el monitoreo): solo se muestran sus advertencias y errores.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    for nombre in ("uvicorn.access", "uvicorn.error", "app"):
        registrador = logging.getLogger(nombre)
        if not any(isinstance(f, FiltroSecretos) for f in registrador.filters):
            registrador.addFilter(FiltroSecretos())
