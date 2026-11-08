"""Catálogo de ubicaciones para origen y destino (RF05)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ubicaciones.modelos import Ubicacion


async def listar_ubicaciones(sesion: AsyncSession) -> list[Ubicacion]:
    return list((await sesion.scalars(select(Ubicacion).order_by(Ubicacion.nombre))).all())
