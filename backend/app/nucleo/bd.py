"""Conexión a PostgreSQL 16 (SQLAlchemy 2 async + psycopg 3) y base declarativa de los modelos.

Los modelos se mapean a las tablas que crea la migración 0001 (``esquema_bd.sql``):
nunca se usa ``Base.metadata.create_all``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Cada conexión trabaja en hora de Colombia, así now() y current_date coinciden con el Reloj.
OPCIONES_CONEXION = {"options": "-c timezone=America/Bogota"}


class Base(AsyncAttrs, DeclarativeBase):
    """Base de los modelos. Los metadatos solo describen tablas existentes."""

    metadata = MetaData()


def crear_motor(url: str, **opciones: object) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args=OPCIONES_CONEXION,
        **opciones,
    )


def crear_fabrica_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor, expire_on_commit=False, autoflush=False)


async def obtener_sesion(request: Request) -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por petición. Al salir se cierra y se deshace lo no confirmado."""
    fabrica: async_sessionmaker[AsyncSession] = request.app.state.contenedor.sesiones
    async with fabrica() as sesion:
        yield sesion
