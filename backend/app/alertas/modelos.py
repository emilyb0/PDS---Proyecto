"""Alertas (RF11, RF16, RF25) y su atención (RF27).

Herencia *joined*: ``alerta`` es la superclase y ``alerta_servicio`` / ``alerta_mantenimiento`` son las
subclases (PK = FK). ``AlertaServicio.atendida`` no es columna: es verdadera si existe su ``atencion_alerta``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dispositivos.modelos import Dispositivo
from app.nucleo.bd import Base
from app.nucleo.enums import PG_CAUSA_ALERTA, PG_TIPO_ALERTA, CausaAlerta, TipoAlerta
from app.servicios.modelos import Incidencia
from app.usuarios.modelos import Usuario


class Alerta(Base):
    """Clase abstracta del diagrama."""

    __tablename__ = "alerta"

    id_alerta: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tipo: Mapped[TipoAlerta] = mapped_column(PG_TIPO_ALERTA)
    id_dispositivo: Mapped[int] = mapped_column(Integer, ForeignKey("dispositivo.id_dispositivo"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    descripcion: Mapped[str] = mapped_column(String(255))

    dispositivo: Mapped[Dispositivo] = relationship(lazy="raise")

    __mapper_args__ = {"polymorphic_on": "tipo", "polymorphic_abstract": True}


class AtencionAlerta(Base):
    __tablename__ = "atencion_alerta"

    id_atencion: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_alerta: Mapped[int] = mapped_column(Integer, ForeignKey("alerta_servicio.id_alerta"))
    id_operador: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id_usuario"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    causa_revisada: Mapped[str] = mapped_column(String(255))
    observaciones: Mapped[str | None] = mapped_column(Text)

    operador: Mapped[Usuario] = relationship(lazy="selectin")


class AlertaServicio(Alerta):
    __tablename__ = "alerta_servicio"

    id_alerta: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerta.id_alerta", ondelete="CASCADE"), primary_key=True
    )
    id_incidencia: Mapped[int] = mapped_column(Integer, ForeignKey("incidencia.id_incidencia"))
    causa: Mapped[CausaAlerta] = mapped_column(PG_CAUSA_ALERTA)

    incidencia: Mapped[Incidencia] = relationship(lazy="raise")
    atencion: Mapped[AtencionAlerta | None] = relationship(lazy="selectin")

    __mapper_args__ = {"polymorphic_identity": TipoAlerta.SERVICIO, "polymorphic_load": "inline"}

    @property
    def atendida(self) -> bool:
        return self.atencion is not None

    def registrar_atencion(
        self, id_operador: int, causa_revisada: str, observaciones: str | None, fecha_hora: datetime
    ) -> AtencionAlerta:
        """RF27: una sola atención por alerta (la BD también lo exige)."""
        return AtencionAlerta(
            id_alerta=self.id_alerta,
            id_operador=id_operador,
            causa_revisada=causa_revisada,
            observaciones=observaciones,
            fecha_hora=fecha_hora,
        )


class AlertaMantenimiento(Alerta):
    __tablename__ = "alerta_mantenimiento"

    id_alerta: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerta.id_alerta", ondelete="CASCADE"), primary_key=True
    )
    dias_desde_ultimo: Mapped[int] = mapped_column(SmallInteger)
    horas_desde_ultimo: Mapped[Decimal] = mapped_column(Numeric(7, 2))

    __mapper_args__ = {"polymorphic_identity": TipoAlerta.MANTENIMIENTO, "polymorphic_load": "inline"}
