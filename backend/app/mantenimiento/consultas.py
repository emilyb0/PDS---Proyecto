"""Consultas sobre la tabla ``mantenimiento`` que usan varios módulos (RF02, RF03, RF15, RF16).

Están en el núcleo porque solo leen el modelo, que es parte del esquema.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.mantenimiento.modelos import Mantenimiento


async def mantenimiento_abierto(sesion: AsyncSession, id_dispositivo: int) -> Mantenimiento | None:
    """El mantenimiento sin fecha de fin del dispositivo, si lo hay (con su responsable cargado)."""
    consulta = (
        select(Mantenimiento)
        .where(Mantenimiento.id_dispositivo == id_dispositivo, Mantenimiento.fecha_fin.is_(None))
        .options(selectinload(Mantenimiento.responsable))
    )
    return await sesion.scalar(consulta)
