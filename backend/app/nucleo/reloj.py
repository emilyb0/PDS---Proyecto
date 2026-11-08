"""Reloj inyectable (especificación, sección 3).

Ningún servicio llama a ``datetime.now()``: todos reciben un ``Reloj``. Las horas son de
America/Bogota y sin zona (``TIMESTAMP`` de PostgreSQL), igual que la sesión de la base.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ZONA_HORARIA = ZoneInfo("America/Bogota")


def a_hora_local(valor: datetime) -> datetime:
    """Convierte una fecha y hora a hora de Colombia sin zona. Si ya viene sin zona, se asume local."""
    if valor.tzinfo is None:
        return valor
    return valor.astimezone(ZONA_HORARIA).replace(tzinfo=None)


def con_zona(valor: datetime) -> datetime:
    """Agrega la zona de Colombia a una hora local sin zona (para serializar con -05:00)."""
    if valor.tzinfo is not None:
        return valor.astimezone(ZONA_HORARIA)
    return valor.replace(tzinfo=ZONA_HORARIA)


class Reloj(ABC):
    """Fuente única de la hora actual."""

    @abstractmethod
    def ahora(self) -> datetime:
        """Hora actual de Colombia, sin zona."""

    def hoy(self) -> date:
        return self.ahora().date()

    def marca_unix(self) -> int:
        """Segundos Unix de la hora actual (para JWT y enlaces firmados)."""
        return int(con_zona(self.ahora()).timestamp())


class RelojSistema(Reloj):
    """Reloj real. Es el único lugar del código que consulta la hora del sistema."""

    def ahora(self) -> datetime:
        return datetime.now(ZONA_HORARIA).replace(tzinfo=None)


class RelojSimulado(Reloj):
    """Reloj controlado por las pruebas: no avanza solo."""

    def __init__(self, inicio: datetime) -> None:
        self._ahora = a_hora_local(inicio)

    def ahora(self) -> datetime:
        return self._ahora

    def fijar(self, momento: datetime) -> None:
        self._ahora = a_hora_local(momento)

    def avanzar(self, **delta: float) -> datetime:
        """Avanza el reloj, por ejemplo ``avanzar(minutes=11)``. Devuelve la nueva hora."""
        self._ahora += timedelta(**delta)
        return self._ahora
