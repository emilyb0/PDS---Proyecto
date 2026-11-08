"""Tipos que comparten el monitor del núcleo y las verificaciones de los módulos (``verificaciones_monitor``)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.dispositivos.modelos import Dispositivo
from app.integraciones.dispositivo.interfaz import TelemetriaDispositivo
from app.nucleo.enums import CausaAlerta
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio


@dataclass(frozen=True)
class CondicionAlerta:
    """Una causa de alerta presente en esta lectura. El núcleo decide si es nueva (sin duplicados) y la guarda."""

    causa: CausaAlerta
    descripcion: str
    latitud: float | None = None
    longitud: float | None = None


@dataclass
class ContextoMonitor:
    """Lo que recibe cada verificación del monitor, una vez por dispositivo y por ciclo, dentro de su transacción.

    Una verificación puede:

    - agregar ``condiciones`` (solo cuentan si el dispositivo tiene un servicio en curso);
    - agregar campos al evento ``telemetria`` en ``datos_telemetria`` (RF25: ``fuera_de_zona``);
    - guardar cambios con ``sesion`` (se confirman junto con la lectura);
    - dejar ``eventos`` SSE y acciones ``despues`` que el núcleo ejecuta después del *commit* (RF24: avisar al robot).
    """

    sesion: AsyncSession
    contenedor: Any
    dispositivo: Dispositivo
    telemetria: TelemetriaDispositivo
    bitacora: BitacoraServicio | None = None
    reserva: Reserva | None = None
    condiciones: list[CondicionAlerta] = field(default_factory=list)
    datos_telemetria: dict[str, Any] = field(default_factory=dict)
    eventos: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    despues: list[Callable[[], Awaitable[None]]] = field(default_factory=list)

    @property
    def en_servicio(self) -> bool:
        return self.bitacora is not None and not self.bitacora.cerrada
