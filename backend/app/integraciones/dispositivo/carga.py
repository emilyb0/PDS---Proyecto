"""Datos iniciales del simulador leídos de la base (RNF10: un dispositivo nuevo aparece solo en el simulador)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dispositivos.modelos import Dispositivo
from app.integraciones.dispositivo.interfaz import Punto
from app.nucleo.enums import EstadoDispositivo, EstadoSensor, TipoDispositivo
from app.ubicaciones.modelos import Ubicacion


@dataclass(frozen=True)
class DatosDispositivo:
    numero_serie: str
    tipo: TipoDispositivo
    nivel_bateria: int
    sensores: dict[str, EstadoSensor]
    estado: EstadoDispositivo = EstadoDispositivo.DISPONIBLE


class CargadorDesdeBD:
    """Le da al simulador lo que un dispositivo real ya sabría de sí mismo: su tipo, batería y sensores."""

    def __init__(self, sesiones: async_sessionmaker[AsyncSession], nombre_base: str) -> None:
        self._sesiones = sesiones
        self._nombre_base = nombre_base

    async def dispositivo(self, numero_serie: str) -> DatosDispositivo | None:
        async with self._sesiones() as sesion:
            d = await sesion.scalar(select(Dispositivo).where(Dispositivo.numero_serie == numero_serie))
            if d is None:
                return None
            return DatosDispositivo(
                d.numero_serie, d.tipo, d.nivel_bateria, {s.nombre: s.estado for s in d.sensores}, d.estado
            )

    async def base(self) -> Punto | None:
        async with self._sesiones() as sesion:
            u = await sesion.scalar(select(Ubicacion).where(Ubicacion.nombre == self._nombre_base))
            return None if u is None else Punto(float(u.latitud), float(u.longitud), u.nombre)
