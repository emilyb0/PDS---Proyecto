"""Planificador de tareas (APScheduler 3.x ``AsyncIOScheduler``, zona America/Bogota).

Arranca con la API si ``TAREAS_ACTIVAS=true``: primero reanuda los servicios abiertos (decisión P1), luego programa
las tareas del catálogo y deja corriendo el consumidor de eventos del dispositivo. Ninguna tarea se solapa consigo
misma (``max_instances=1``) y las ejecuciones atrasadas se juntan en una (``coalesce``).

APScheduler usa la hora del sistema solo para decidir **cuándo** correr; las reglas de negocio usan el ``Reloj``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.nucleo.extensiones import TareaProgramada
from app.nucleo.reloj import ZONA_HORARIA
from app.tareas.catalogo import todas_las_tareas

if TYPE_CHECKING:
    from app.contenedor import Contenedor

registro = logging.getLogger(__name__)


class Planificador:
    def __init__(self, contenedor: Contenedor) -> None:
        self.c = contenedor
        self._programador: AsyncIOScheduler | None = None
        self._consumidor: asyncio.Task[None] | None = None

    @property
    def activo(self) -> bool:
        return self._programador is not None and self._programador.running

    @property
    def consumidor_vivo(self) -> bool:
        return self._consumidor is not None and not self._consumidor.done()

    def _disparador(self, tarea: TareaProgramada) -> IntervalTrigger | CronTrigger:
        if tarea.tipo == "intervalo":
            return IntervalTrigger(seconds=tarea.segundos or 60, timezone=ZONA_HORARIA)
        return CronTrigger(hour=tarea.hora or 0, minute=tarea.minuto, timezone=ZONA_HORARIA)

    async def _ejecutar(self, tarea: TareaProgramada) -> None:
        try:
            resultado = await tarea.funcion(self.c)
            if tarea.tipo == "diaria" or tarea.nombre == "reintento-subidas":
                registro.info("Tarea %s: %s", tarea.nombre, resultado)
        except Exception:
            registro.exception("Falló la tarea %s", tarea.nombre)

    async def iniciar(self) -> None:
        try:
            await self.c.monitor.reanudar_servicios()
        except Exception:
            registro.exception("No se pudieron reanudar los servicios abiertos")
        programador = AsyncIOScheduler(timezone=ZONA_HORARIA)
        for tarea in todas_las_tareas(self.c).values():
            programador.add_job(
                self._ejecutar,
                self._disparador(tarea),
                args=[tarea],
                id=tarea.nombre,
                name=tarea.nombre,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30 if tarea.tipo == "intervalo" else 3600,
            )
        programador.start()
        self._programador = programador
        self._consumidor = asyncio.create_task(self.c.monitor.consumir_eventos(), name="eventos-dispositivo")
        registro.info("Tareas programadas: %s", ", ".join(todas_las_tareas(self.c)))

    async def detener(self) -> None:
        if self._programador is not None and self._programador.running:
            self._programador.shutdown(wait=False)
        self._programador = None
        if self._consumidor is not None:
            self._consumidor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumidor
        self._consumidor = None
