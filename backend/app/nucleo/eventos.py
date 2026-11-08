"""``BusEventos``: reparte los eventos de tiempo real a los navegadores conectados por SSE (RF10, RNF02).

- Cada evento tiene un ``id`` incremental, un ``tipo`` (``telemetria``, ``alerta``, ``servicio``…) y ``datos`` en JSON.
- Guarda los últimos ``capacidad_historial`` eventos para reenviarlos cuando el navegador se reconecta con
  ``Last-Event-ID``.
- Vive en memoria: por eso Uvicorn corre con un solo worker.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.nucleo.reloj import con_zona

registro = logging.getLogger(__name__)


def a_json(valor: Any) -> Any:
    """Convierte los datos de un evento a tipos JSON (fechas con -05:00, como en la API)."""
    if isinstance(valor, BaseModel):
        return valor.model_dump(mode="json")
    if isinstance(valor, datetime):
        return con_zona(valor).isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple | set):
        return [a_json(v) for v in valor]
    return valor


@dataclass(frozen=True)
class EventoSSE:
    id: int
    tipo: str
    datos: dict[str, Any]


class Suscripcion:
    """Cola de eventos de un navegador conectado."""

    def __init__(self, capacidad: int) -> None:
        self.cola: asyncio.Queue[EventoSSE] = asyncio.Queue(maxsize=capacidad)
        self.desbordada = False

    async def siguiente(self, espera: float) -> EventoSSE | None:
        """El próximo evento, o ``None`` si no llega ninguno en ``espera`` segundos."""
        try:
            return await asyncio.wait_for(self.cola.get(), timeout=espera)
        except TimeoutError:
            return None


class BusEventos:
    def __init__(self, capacidad_historial: int = 200, capacidad_cola: int = 1000) -> None:
        self._historial: deque[EventoSSE] = deque(maxlen=capacidad_historial)
        self._suscripciones: set[Suscripcion] = set()
        self._ultimo_id = 0
        self._capacidad_cola = capacidad_cola

    @property
    def ultimo_id(self) -> int:
        return self._ultimo_id

    @property
    def conectados(self) -> int:
        return len(self._suscripciones)

    def publicar(self, tipo: str, datos: dict[str, Any] | BaseModel) -> EventoSSE:
        self._ultimo_id += 1
        evento = EventoSSE(self._ultimo_id, tipo, a_json(datos))
        self._historial.append(evento)
        for suscripcion in list(self._suscripciones):
            try:
                suscripcion.cola.put_nowait(evento)
            except asyncio.QueueFull:
                # Un navegador que no lee: se le cierra el flujo y, al reconectarse, recupera lo que falte.
                suscripcion.desbordada = True
                self._suscripciones.discard(suscripcion)
                registro.warning("Se cerró un flujo SSE que no leía los eventos (cola llena).")
        return evento

    def historial(self, desde_id: int = 0, tipo: str | None = None) -> list[EventoSSE]:
        """Eventos guardados con id mayor que ``desde_id`` (opcionalmente de un tipo)."""
        return [e for e in self._historial if e.id > desde_id and (tipo is None or e.tipo == tipo)]

    @contextmanager
    def suscribir(self, ultimo_id: int | None = None) -> Iterator[Suscripcion]:
        """Abre una suscripción. Con ``ultimo_id`` (``Last-Event-ID``) primero entrega los eventos que faltaron."""
        suscripcion = Suscripcion(self._capacidad_cola)
        if ultimo_id is not None:
            for evento in self.historial(ultimo_id)[-self._capacidad_cola :]:
                suscripcion.cola.put_nowait(evento)
        self._suscripciones.add(suscripcion)
        try:
            yield suscripcion
        finally:
            self._suscripciones.discard(suscripcion)
