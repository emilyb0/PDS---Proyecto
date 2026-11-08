"""Reserva → tabla ``reserva`` (RF05, RF06, RF21, RF22, RF24).

``horario`` es una columna calculada por PostgreSQL (``TSRANGE [inicio, fin)``): nunca se escribe.
La restricción ``ex_reserva_cruce`` impide cruces entre reservas PROGRAMADA o EN_CURSO del mismo dispositivo.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import TSRANGE
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dispositivos.modelos import Dispositivo
from app.nucleo.bd import Base
from app.nucleo.enums import PG_ESTADO_RESERVA, PG_TIPO_SERVICIO, EstadoReserva, TipoServicio
from app.ubicaciones.modelos import Ubicacion
from app.usuarios.modelos import Usuario

if TYPE_CHECKING:
    from app.servicios.modelos import BitacoraServicio


class Reserva(Base):
    __tablename__ = "reserva"

    id_reserva: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_administrador: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id_usuario"))
    id_operador: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id_usuario"))
    id_dispositivo: Mapped[int] = mapped_column(Integer, ForeignKey("dispositivo.id_dispositivo"))
    id_origen: Mapped[int] = mapped_column(Integer, ForeignKey("ubicacion.id_ubicacion"))
    id_destino: Mapped[int] = mapped_column(Integer, ForeignKey("ubicacion.id_ubicacion"))
    tipo_servicio: Mapped[TipoServicio] = mapped_column(PG_TIPO_SERVICIO)
    fecha: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time] = mapped_column(Time)
    duracion_estimada_min: Mapped[int] = mapped_column(SmallInteger)
    horario: Mapped[Any] = mapped_column(
        TSRANGE,
        Computed(
            "tsrange(fecha + hora_inicio, fecha + hora_inicio + duracion_estimada_min * INTERVAL '1 minute')",
            persisted=True,
        ),
    )
    estado: Mapped[EstadoReserva] = mapped_column(PG_ESTADO_RESERVA, default=EstadoReserva.PROGRAMADA)
    codigo_entrega: Mapped[str | None] = mapped_column(CHAR(4))
    motivo_cambio: Mapped[str | None] = mapped_column(String(255))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime)

    administrador: Mapped[Usuario] = relationship(foreign_keys=[id_administrador], lazy="raise")
    operador: Mapped[Usuario] = relationship(foreign_keys=[id_operador], lazy="raise")
    dispositivo: Mapped[Dispositivo] = relationship(lazy="raise")
    origen: Mapped[Ubicacion] = relationship(foreign_keys=[id_origen], lazy="raise")
    destino: Mapped[Ubicacion] = relationship(foreign_keys=[id_destino], lazy="raise")
    bitacora: Mapped[BitacoraServicio | None] = relationship(back_populates="reserva", lazy="raise")

    # ------------------------------------------------------------------ reglas del diagrama

    @property
    def inicio(self) -> datetime:
        return datetime.combine(self.fecha, self.hora_inicio)

    @property
    def fin(self) -> datetime:
        return self.inicio + timedelta(minutes=self.duracion_estimada_min)

    def hora_fin(self) -> time:
        return self.fin.time()

    def se_cruza_con(self, otra: Reserva) -> bool:
        """RF06: los rangos [inicio, fin) se cruzan; las reservas contiguas no se cruzan."""
        return self.inicio < otra.fin and otra.inicio < self.fin

    @staticmethod
    def generar_codigo_entrega() -> str:
        """RF24: código de 4 dígitos con ``secrets`` (criptográficamente aleatorio)."""
        return f"{secrets.randbelow(10_000):04d}"

    def cancelar(self, motivo: str) -> None:
        self.estado = EstadoReserva.CANCELADA
        self.motivo_cambio = motivo

    def reprogramar(self, fecha: date, hora_inicio: time, motivo: str, duracion_min: int | None = None) -> None:
        self.fecha = fecha
        self.hora_inicio = hora_inicio
        if duracion_min is not None:
            self.duracion_estimada_min = duracion_min
        self.motivo_cambio = motivo
