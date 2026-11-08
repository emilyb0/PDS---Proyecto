"""Registro y consulta de la auditoría (RNF09).

``registrar_auditoria`` agrega la fila a la sesión del caso de uso: queda en la MISMA transacción que la
creación, edición o baja, y si esa transacción falla, la auditoría tampoco se guarda.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auditoria.modelos import RegistroAuditoria
from app.nucleo.enums import AccionAuditoria
from app.nucleo.errores import ErrorValidacion
from app.nucleo.esquemas import Pagina, ParametrosPaginacion
from app.nucleo.paginacion import paginar
from app.nucleo.reloj import Reloj
from app.usuarios.modelos import Usuario


def registrar_auditoria(
    sesion: AsyncSession,
    reloj: Reloj,
    usuario: Usuario,
    accion: AccionAuditoria,
    entidad: str,
    id_entidad: int,
) -> RegistroAuditoria:
    """Agrega un registro de auditoría a la transacción en curso. ``entidad`` es el nombre de la tabla."""
    registro = RegistroAuditoria(
        id_usuario=usuario.id_usuario,
        fecha_hora=reloj.ahora(),
        accion=accion,
        entidad=entidad,
        id_entidad=id_entidad,
    )
    sesion.add(registro)
    return registro


async def consultar_auditoria(
    sesion: AsyncSession,
    paginacion: ParametrosPaginacion,
    *,
    id_usuario: int | None = None,
    entidad: str | None = None,
    accion: AccionAuditoria | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> Pagina[RegistroAuditoria]:
    if desde and hasta and desde > hasta:
        raise ErrorValidacion.de_campo("desde", "La fecha inicial no puede ser posterior a la final.")
    consulta = select(RegistroAuditoria).options(joinedload(RegistroAuditoria.usuario))
    if id_usuario is not None:
        consulta = consulta.where(RegistroAuditoria.id_usuario == id_usuario)
    if entidad:
        consulta = consulta.where(RegistroAuditoria.entidad == entidad)
    if accion is not None:
        consulta = consulta.where(RegistroAuditoria.accion == accion)
    if desde is not None:
        consulta = consulta.where(RegistroAuditoria.fecha_hora >= desde)
    if hasta is not None:
        consulta = consulta.where(RegistroAuditoria.fecha_hora < hasta + timedelta(days=1))
    consulta = consulta.order_by(RegistroAuditoria.fecha_hora.desc(), RegistroAuditoria.id_auditoria.desc())
    return await paginar(sesion, consulta, paginacion, lambda fila: fila)
