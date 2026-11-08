"""Servidor Uvicorn real dentro del loop de las pruebas, para el SSE y la prueba lenta de RNF02.

``httpx.ASGITransport`` espera a que la respuesta termine, y un flujo SSE no termina; por eso estas pruebas
levantan un servidor de verdad en un puerto libre de 127.0.0.1.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import uvicorn
from fastapi import FastAPI


@asynccontextmanager
async def servidor_real(app: FastAPI) -> AsyncIterator[str]:
    """Levanta la app y devuelve su URL base. Al salir la detiene."""
    enchufe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    enchufe.bind(("127.0.0.1", 0))
    puerto = enchufe.getsockname()[1]
    config = uvicorn.Config(app, log_level="warning", lifespan="on", timeout_graceful_shutdown=2)
    servidor = uvicorn.Server(config)
    servidor.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    tarea = asyncio.create_task(servidor.serve(sockets=[enchufe]))
    for _ in range(200):
        if servidor.started:
            break
        await asyncio.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{puerto}"
    finally:
        servidor.should_exit = True
        await asyncio.wait_for(tarea, timeout=10)


@dataclass
class EventoRecibido:
    tipo: str
    id: str | None
    datos: dict


async def leer_sse(respuesta: httpx.Response, destino: list[EventoRecibido], comentarios: list[str]) -> None:
    """Lee el flujo SSE y va guardando los eventos (y los comentarios, como ``: ping``) hasta que se cierre."""
    tipo, ident, datos = "message", None, []
    async for linea in respuesta.aiter_lines():
        if linea == "":
            if datos:
                destino.append(EventoRecibido(tipo, ident, json.loads("\n".join(datos))))
            tipo, ident, datos = "message", None, []
        elif linea.startswith(":"):
            comentarios.append(linea[1:].strip())
        elif linea.startswith("event:"):
            tipo = linea.removeprefix("event:").strip()
        elif linea.startswith("id:"):
            ident = linea.removeprefix("id:").strip()
        elif linea.startswith("data:"):
            datos.append(linea.removeprefix("data:").strip())


async def esperar(condicion, tiempo: float = 5.0) -> None:
    """Espera (sin bloquear el loop) a que ``condicion()`` sea verdadera."""
    for _ in range(int(tiempo / 0.02)):
        if condicion():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("La condición no se cumplió a tiempo.")
