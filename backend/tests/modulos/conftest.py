"""Pruebas de los módulos removibles de la entrega 2: corren con todos los módulos encendidos.

Todavía no hay módulos: cada RF pendiente agrega aquí su carpeta ``rfXX_nombre/`` (docs/arquitectura.md).
"""

from __future__ import annotations

import pytest

from app.modulos import seleccionar_modulos
from app.nucleo.extensiones import ModuloRF


@pytest.fixture
def modulos_activos() -> list[ModuloRF]:
    return seleccionar_modulos("todos")
