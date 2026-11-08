"""Mantenimiento → tabla ``mantenimiento`` (RF15, RF16)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Identity, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dispositivos.modelos import Dispositivo
from app.nucleo.bd import Base
from app.nucleo.enums import PG_TIPO_MANTENIMIENTO, TipoMantenimiento
from app.usuarios.modelos import Usuario


class Mantenimiento(Base):
    __tablename__ = "mantenimiento"

    id_mantenimiento: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_dispositivo: Mapped[int] = mapped_column(Integer, ForeignKey("dispositivo.id_dispositivo"))
    id_operador: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id_usuario"))
    tipo: Mapped[TipoMantenimiento] = mapped_column(PG_TIPO_MANTENIMIENTO)
    descripcion: Mapped[str] = mapped_column(Text)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)

    dispositivo: Mapped[Dispositivo] = relationship(lazy="raise")
    responsable: Mapped[Usuario] = relationship(lazy="raise")

    @property
    def abierto(self) -> bool:
        return self.fecha_fin is None

    def cerrar(self, fecha_fin: date) -> None:
        self.fecha_fin = fecha_fin
