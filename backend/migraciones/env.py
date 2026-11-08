"""Entorno de Alembic en modo async.

- La URL sale de ``sqlalchemy.url`` si se pasa por configuración (pruebas); si no, de ``ConfiguracionBD``:
  ``BD_URL`` dentro de Docker (``db:5432``) o ``127.0.0.1:PUERTO_BD`` en la máquina.
- Cada conexión trabaja en hora de Colombia.
- No hay ``target_metadata``: las migraciones se escriben a mano porque el esquema manda sobre los modelos.
"""

from __future__ import annotations

import asyncio
import sys

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import ConfiguracionBD

configuracion = context.config
OPCIONES_CONEXION = {"options": "-c timezone=America/Bogota"}


def _url() -> str:
    return configuracion.get_main_option("sqlalchemy.url") or ConfiguracionBD().url_bd


def _migrar(conexion) -> None:
    context.configure(connection=conexion, target_metadata=None, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _migrar_async() -> None:
    motor = create_async_engine(_url(), connect_args=OPCIONES_CONEXION)
    try:
        async with motor.connect() as conexion:
            await conexion.run_sync(_migrar)
            await conexion.commit()
    finally:
        await motor.dispose()


def _ejecutar_offline() -> None:
    context.configure(url=_url(), target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    _ejecutar_offline()
else:
    # psycopg en modo async no funciona con el ProactorEventLoop de Windows (decisión T10).
    fabrica = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_migrar_async(), loop_factory=fabrica)
