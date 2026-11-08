"""Arranque local sin Docker: ``uv run python -m app`` (desde la carpeta backend).

Escucha en ``127.0.0.1:PUERTO_API`` (del ``.env``; 8010 por defecto) y se conecta a la base de Compose en
``127.0.0.1:PUERTO_BD``. Antes de arrancar la API de Docker hay que detenerla (``docker compose stop api``)
para no usar el mismo puerto.

En Windows usa el *selector event loop*, porque psycopg en modo async no funciona con el
``ProactorEventLoop`` predeterminado (decisión T10). Siempre con un solo worker.
"""

from __future__ import annotations

import asyncio
import os
import sys

import uvicorn

from app.config import Configuracion


def main() -> None:
    config = uvicorn.Config(
        "app.main:crear_app",
        factory=True,
        host=os.environ.get("HOST_API", "127.0.0.1"),
        port=Configuracion().puerto_api,
        workers=1,
    )
    servidor = uvicorn.Server(config)
    fabrica = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=fabrica) as corredor:
        corredor.run(servidor.serve())


if __name__ == "__main__":
    main()
