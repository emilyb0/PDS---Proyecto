"""RNF02 — Prueba de humo (lenta): con 6 dispositivos en servicio, cada uno se actualiza en ≤ 5 s por SSE.

Levanta la API real con las tareas programadas encendidas (APScheduler) y mide en el navegador simulado (un
cliente SSE) cada cuánto llega la telemetría de cada dispositivo. Solo corre con ``pytest --lentas``.
"""

from __future__ import annotations

import asyncio
import contextlib
import time as reloj_pared
from collections import defaultdict
from datetime import time
from itertools import pairwise

import httpx
import pytest

from app.contenedor import Contenedor
from app.nucleo.enums import TipoDispositivo
from app.nucleo.reloj import RelojSimulado
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_ubicaciones, encabezados, servicio_en_curso
from tests.servidor import EventoRecibido, leer_sse, servidor_real

MARGEN_SEG = 0.75  # el planificador corre cada 5 s; se tolera el retraso de la propia vuelta


@pytest.mark.lenta
async def test_rnf02_seis_dispositivos_en_servicio_se_actualizan_cada_5_segundos(
    app, contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, operador: Usuario
) -> None:
    lugares = await crear_ubicaciones(contenedor)
    for i in range(6):
        await servicio_en_curso(
            contenedor,
            administrador=admin,
            operador=operador,
            lugares=lugares,
            tipo=TipoDispositivo.ROBOT if i % 2 else TipoDispositivo.DRONE,
            hora_inicio=time(10, 0),
            duracion_min=60,
        )
    contenedor.config = contenedor.config.model_copy(update={"tareas_activas": True})

    async def avanzar_reloj() -> None:  # el reloj simulado sigue al de pared
        while True:
            await asyncio.sleep(0.5)
            reloj.avanzar(seconds=0.5)

    llegadas: dict[int, list[float]] = defaultdict(list)
    recibidos: list[EventoRecibido] = []
    token = encabezados(contenedor, operador)["Authorization"].removeprefix("Bearer ")
    tic = asyncio.create_task(avanzar_reloj())
    try:
        async with (
            servidor_real(app) as url,
            httpx.AsyncClient(base_url=url, timeout=30) as http,
            http.stream("GET", "/api/monitoreo/stream", params={"token": token}) as respuesta,
        ):
            conectado = reloj_pared.monotonic()
            lector = asyncio.create_task(leer_sse(respuesta, recibidos, []))
            vistos = 0
            while reloj_pared.monotonic() - conectado < 16:
                await asyncio.sleep(0.05)
                for evento in recibidos[vistos:]:
                    if evento.tipo == "telemetria":
                        llegadas[evento.datos["id_dispositivo"]].append(reloj_pared.monotonic())
                vistos = len(recibidos)
            lector.cancel()
    finally:
        tic.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tic

    assert len(llegadas) == 6
    for momentos in llegadas.values():
        assert len(momentos) >= 3
        assert momentos[0] - conectado <= 5 + MARGEN_SEG
        separaciones = [b - a for a, b in pairwise(momentos)]
        assert max(separaciones) <= 5 + MARGEN_SEG, separaciones
