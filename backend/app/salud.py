"""``GET /health``: estado de la API y sus dependencias (RNF06)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app import VERSION
from app.ubicaciones.modelos import Ubicacion

router = APIRouter(tags=["Salud"])
registro = logging.getLogger(__name__)


async def _revisar_bd(request: Request) -> str:
    try:
        async with request.app.state.contenedor.sesiones() as sesion:
            await asyncio.wait_for(sesion.execute(text("SELECT 1")), timeout=3)
        return "ok"
    except Exception as error:
        registro.warning("La base de datos no responde en /health: %s", error)
        return "error"


async def _revisar_almacenamiento(request: Request) -> str:
    try:
        await asyncio.wait_for(request.app.state.contenedor.almacenamiento.revisar(), timeout=3)
        return "ok"
    except Exception as error:
        registro.warning("El almacenamiento de videos no responde en /health: %s", error)
        return "error"


async def _revisar_simulador(request: Request) -> str:
    """``ok``; ``detenido`` si las tareas deberían correr y el consumidor de eventos murió; ``sin_base`` si no
    existe la ubicación base (los dispositivos no tendrían de dónde salir)."""
    contenedor = request.app.state.contenedor
    planificador = getattr(request.app.state, "planificador", None)
    if contenedor.config.tareas_activas and planificador is not None and not planificador.consumidor_vivo:
        return "detenido"
    async with contenedor.sesiones() as sesion:
        base = await sesion.scalar(
            select(Ubicacion.id_ubicacion).where(Ubicacion.nombre == contenedor.config.base_ubicacion)
        )
    return "ok" if base is not None else "sin_base"


# Si falla uno de estos, el servicio no puede atender: responde 503.
CRITICOS = {"base_datos", "almacenamiento"}


@router.get(
    "/health",
    summary="Estado del servicio (RNF06)",
    description="RNF06. Público. Revisa la base de datos, el almacenamiento de videos y el simulador (los módulos "
    "activos agregan los suyos, por ejemplo `zona_operacion` de RF25). `estado` es `ok` si todo está bien y "
    "`degradado` si algo falla; responde 503 solo si falla una dependencia crítica (base de datos o "
    "almacenamiento).",
)
async def salud(request: Request) -> JSONResponse:
    contenedor = request.app.state.contenedor
    componentes = {
        "base_datos": await _revisar_bd(request),
        "almacenamiento": await _revisar_almacenamiento(request),
    }
    try:
        componentes["simulador"] = await asyncio.wait_for(_revisar_simulador(request), timeout=3)
    except Exception as error:
        registro.warning("Falló el chequeo del simulador: %s", error)
        componentes["simulador"] = "error"
    for nombre, chequeo in contenedor.extensiones.chequeos_salud.items():
        try:
            componentes[nombre] = await asyncio.wait_for(chequeo(contenedor), timeout=3)
        except Exception as error:
            registro.warning("Falló el chequeo de salud '%s': %s", nombre, error)
            componentes[nombre] = "error"
    sano = all(valor == "ok" for valor in componentes.values())
    critico_caido = any(componentes.get(nombre, "ok") != "ok" for nombre in CRITICOS)
    cuerpo = {"estado": "ok" if sano else "degradado", **componentes, "version": VERSION}
    return JSONResponse(status_code=503 if critico_caido else 200, content=cuerpo)
