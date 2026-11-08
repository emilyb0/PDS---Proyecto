"""Funciones (permisos de interfaz) de cada rol (RF20, RNF01; especificación, sección 5).

El frontend arma el menú con esta lista; el backend hace cumplir los permisos con ``solo_administrador``.
Aquí están las funciones del núcleo (entrega 1). Cada módulo de la entrega 2 agrega las suyas con
``Extensiones.agregar_funciones`` (por ejemplo ``mantenimiento.gestionar`` de RF15).
"""

from __future__ import annotations

from app.nucleo.enums import RolUsuario
from app.nucleo.extensiones import Extensiones

FUNCIONES_OPERADOR = [
    "inventario.ver",
    "reservas.ver",
    "bitacoras.ver",
    "monitoreo.ver",
    "alertas.ver",
]

FUNCIONES_SOLO_ADMINISTRADOR = [
    "inventario.gestionar",
    "reservas.gestionar",
    "usuarios.gestionar",
    "auditoria.ver",
]


def funciones_de(rol: RolUsuario, modo_demo: bool = False, extensiones: Extensiones | None = None) -> list[str]:
    extras = extensiones.funciones[rol] if extensiones is not None else []
    if rol == RolUsuario.OPERADOR:
        return FUNCIONES_OPERADOR + [f for f in extras if f not in FUNCIONES_OPERADOR]
    funciones = FUNCIONES_OPERADOR + FUNCIONES_SOLO_ADMINISTRADOR
    funciones += [f for f in extras if f not in funciones]
    if modo_demo:
        funciones.append("demo.usar")
    return funciones
