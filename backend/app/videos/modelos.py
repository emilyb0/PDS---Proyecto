"""Video → tabla ``video`` (RF12, RF13, RF26, RNF04).

``url`` guarda la ubicación del objeto en el almacenamiento (por ejemplo ``s3://bucket/videos/…``),
no una URL pública: el bucket es privado.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dominio.fechas import sumar_meses
from app.nucleo.bd import Base
from app.servicios.modelos import BitacoraServicio


class Video(Base):
    __tablename__ = "video"

    id_video: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_bitacora: Mapped[int] = mapped_column(Integer, ForeignKey("bitacora_servicio.id_bitacora"))
    url: Mapped[str] = mapped_column(String(500))
    formato: Mapped[str] = mapped_column(String(10), default="MP4")
    fecha_grabacion: Mapped[datetime] = mapped_column(DateTime)
    duracion_seg: Mapped[int] = mapped_column(Integer)
    fecha_eliminacion: Mapped[date | None] = mapped_column(Date)

    bitacora: Mapped[BitacoraServicio] = relationship(back_populates="video", lazy="raise")

    @property
    def eliminado(self) -> bool:
        return self.fecha_eliminacion is not None

    def esta_vencido(self, hoy: date, meses: int = 3) -> bool:
        """RF26: vence cuando ``fecha_grabacion + meses ≤ hoy`` (meses de calendario, decisión D16)."""
        return sumar_meses(self.fecha_grabacion.date(), meses) <= hoy
