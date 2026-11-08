"""Bitácora del servicio, telemetría e incidencias (RF08–RF11, RF14, RF24, RF25).

Tablas: ``bitacora_servicio``, ``registro_telemetria``, ``lectura_sensor`` (el Map de sensores del diagrama)
e ``incidencia``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dispositivos.modelos import Sensor
from app.nucleo.bd import Base
from app.nucleo.enums import (
    PG_ESTADO_SENSOR,
    PG_ESTADO_SERVICIO,
    PG_TIPO_INCIDENCIA,
    EstadoSensor,
    EstadoServicio,
    TipoIncidencia,
)
from app.reservas.modelos import Reserva

if TYPE_CHECKING:
    from app.videos.modelos import Video


class LecturaSensor(Base):
    __tablename__ = "lectura_sensor"

    id_telemetria: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("registro_telemetria.id_telemetria", ondelete="CASCADE"), primary_key=True
    )
    id_sensor: Mapped[int] = mapped_column(Integer, ForeignKey("sensor.id_sensor"), primary_key=True)
    estado: Mapped[EstadoSensor] = mapped_column(PG_ESTADO_SENSOR)

    sensor: Mapped[Sensor] = relationship(lazy="raise")


class RegistroTelemetria(Base):
    """Un punto de la ruta recorrida."""

    __tablename__ = "registro_telemetria"

    id_telemetria: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    id_bitacora: Mapped[int] = mapped_column(Integer, ForeignKey("bitacora_servicio.id_bitacora", ondelete="CASCADE"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    latitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    nivel_bateria: Mapped[int] = mapped_column(SmallInteger)
    estado_servicio: Mapped[str] = mapped_column(String(40))

    lecturas: Mapped[list[LecturaSensor]] = relationship(cascade="all, delete-orphan", lazy="raise")


class Incidencia(Base):
    __tablename__ = "incidencia"

    id_incidencia: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_bitacora: Mapped[int] = mapped_column(Integer, ForeignKey("bitacora_servicio.id_bitacora", ondelete="CASCADE"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    tipo: Mapped[TipoIncidencia] = mapped_column(PG_TIPO_INCIDENCIA)
    descripcion: Mapped[str] = mapped_column(Text)
    latitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))


class BitacoraServicio(Base):
    __tablename__ = "bitacora_servicio"

    id_bitacora: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_reserva: Mapped[int] = mapped_column(Integer, ForeignKey("reserva.id_reserva"))
    hora_salida: Mapped[datetime] = mapped_column(DateTime)
    hora_regreso: Mapped[datetime | None] = mapped_column(DateTime)
    hora_entrega: Mapped[datetime | None] = mapped_column(DateTime)
    estado: Mapped[EstadoServicio] = mapped_column(PG_ESTADO_SERVICIO, default=EstadoServicio.EN_CURSO)

    reserva: Mapped[Reserva] = relationship(back_populates="bitacora", lazy="raise")
    incidencias: Mapped[list[Incidencia]] = relationship(order_by=Incidencia.fecha_hora, lazy="raise")
    video: Mapped[Video | None] = relationship(back_populates="bitacora", lazy="raise")

    # ------------------------------------------------------------------ reglas del diagrama

    @property
    def cerrada(self) -> bool:
        return self.estado == EstadoServicio.FINALIZADO

    @property
    def entregado(self) -> bool:
        """El servicio fue entregado si tiene hora de entrega, aunque el estado final sea FINALIZADO."""
        return self.hora_entrega is not None

    def registrar_punto(
        self,
        fecha_hora: datetime,
        latitud: float,
        longitud: float,
        nivel_bateria: int,
        estado_servicio: str,
        lecturas: dict[int, EstadoSensor],
    ) -> RegistroTelemetria:
        """Crea un punto de la ruta con el estado de cada sensor (``lecturas``: id_sensor → estado)."""
        return RegistroTelemetria(
            id_bitacora=self.id_bitacora,
            fecha_hora=fecha_hora,
            latitud=Decimal(str(round(latitud, 6))),
            longitud=Decimal(str(round(longitud, 6))),
            nivel_bateria=nivel_bateria,
            estado_servicio=estado_servicio,
            lecturas=[LecturaSensor(id_sensor=id_sensor, estado=estado) for id_sensor, estado in lecturas.items()],
        )

    def registrar_incidencia(
        self,
        tipo: TipoIncidencia,
        descripcion: str,
        fecha_hora: datetime,
        latitud: float | None = None,
        longitud: float | None = None,
    ) -> Incidencia:
        return Incidencia(
            id_bitacora=self.id_bitacora,
            tipo=tipo,
            descripcion=descripcion,
            fecha_hora=fecha_hora,
            latitud=None if latitud is None else Decimal(str(round(latitud, 6))),
            longitud=None if longitud is None else Decimal(str(round(longitud, 6))),
        )

    def confirmar_entrega(self, codigo: str, codigo_esperado: str | None, ahora: datetime) -> bool:
        """RF24: si el código coincide, el servicio queda ENTREGADO con la hora de entrega."""
        if codigo_esperado is None or codigo != codigo_esperado:
            return False
        self.estado = EstadoServicio.ENTREGADO
        self.hora_entrega = ahora
        return True

    def cerrar(self, hora_regreso: datetime) -> None:
        self.hora_regreso = hora_regreso
        self.estado = EstadoServicio.FINALIZADO

    def horas_uso(self) -> float | None:
        if self.hora_regreso is None:
            return None
        return round((self.hora_regreso - self.hora_salida).total_seconds() / 3600, 2)
