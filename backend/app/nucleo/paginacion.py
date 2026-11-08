"""Paginación con ``limite`` y ``desplazamiento`` (especificación, sección 9)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nucleo.esquemas import Pagina, ParametrosPaginacion


async def paginar[T](
    sesion: AsyncSession,
    consulta: Select[Any],
    paginacion: ParametrosPaginacion,
    transformar: Callable[[Any], T],
    *,
    escalares: bool = True,
) -> Pagina[T]:
    """Cuenta el total, trae la página pedida y transforma cada fila al esquema de salida."""
    total = await sesion.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    pagina = consulta.limit(paginacion.limite).offset(paginacion.desplazamiento)
    filas: Sequence[Any] = (await sesion.scalars(pagina)).all() if escalares else (await sesion.execute(pagina)).all()
    return Pagina[T](
        items=[transformar(fila) for fila in filas],
        total=total or 0,
        limite=paginacion.limite,
        desplazamiento=paginacion.desplazamiento,
    )
