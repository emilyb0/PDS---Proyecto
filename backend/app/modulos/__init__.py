"""Módulos removibles de la entrega 2: un paquete ``rfXX_nombre`` por requisito.

En esta copia (entrega 1) todavía no hay ninguno: este archivo es solo el mecanismo que los descubre. Para
implementar un RF pendiente como módulo, vea ``docs/como-continuar.md`` y ``docs/arquitectura.md``.

Se descubren solos: para quitar un módulo basta con borrar su carpeta (y la de sus pruebas). Para apagarlo sin
borrar código, use ``MODULOS_ACTIVOS`` en el ``.env``: ``todos`` (por defecto), ``ninguno`` (solo la entrega 1) o
una lista separada por comas, por ejemplo ``rf02,rf03,rf15``.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache

from app.nucleo.extensiones import ModuloRF

_SIN_MODULOS = {"ninguno", "entrega1", "entrega-1", ""}


@cache
def modulos_disponibles() -> dict[str, ModuloRF]:
    """Todos los módulos presentes en ``app/modulos``, por clave (``rf02``…), en orden."""
    encontrados: dict[str, ModuloRF] = {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        if not (info.ispkg and info.name.startswith("rf")):
            continue
        paquete = importlib.import_module(f"{__name__}.{info.name}")
        modulo = getattr(paquete, "MODULO", None)
        if not isinstance(modulo, ModuloRF):
            raise RuntimeError(f"El paquete app.modulos.{info.name} debe definir MODULO = ModuloRF(...).")
        encontrados[modulo.clave] = modulo
    return encontrados


def seleccionar_modulos(valor: str) -> list[ModuloRF]:
    """Interpreta ``MODULOS_ACTIVOS``."""
    texto = valor.strip().lower()
    disponibles = modulos_disponibles()
    if texto in _SIN_MODULOS:
        return []
    if texto == "todos":
        return list(disponibles.values())
    claves = [c.strip() for c in texto.split(",") if c.strip()]
    desconocidos = [c for c in claves if c not in disponibles]
    if desconocidos:
        raise ValueError(
            f"MODULOS_ACTIVOS tiene módulos que no existen: {', '.join(desconocidos)}. "
            f"Disponibles: {', '.join(disponibles) or 'ninguno'}."
        )
    return [disponibles[c] for c in claves]
