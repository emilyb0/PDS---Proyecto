"""Ubicacion y ZonaOperacion → tablas ``ubicacion``, ``zona_operacion`` y ``vertice_zona`` (RF05, RF25)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Identity, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dominio.geometria import punto_en_poligono
from app.nucleo.bd import Base


class Ubicacion(Base):
    """Catálogo de puntos del campus para origen y destino."""

    __tablename__ = "ubicacion"

    id_ubicacion: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    latitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))


class VerticeZona(Base):
    __tablename__ = "vertice_zona"

    id_zona: Mapped[int] = mapped_column(
        Integer, ForeignKey("zona_operacion.id_zona", ondelete="CASCADE"), primary_key=True
    )
    orden: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    latitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))


class ZonaOperacion(Base):
    """Polígono de la zona de operación del campus (sus ``limites`` son los vértices en orden)."""

    __tablename__ = "zona_operacion"

    id_zona: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))

    vertices: Mapped[list[VerticeZona]] = relationship(
        order_by=VerticeZona.orden, cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def limites(self) -> list[tuple[float, float]]:
        return [(float(v.latitud), float(v.longitud)) for v in self.vertices]

    def contiene(self, latitud: float, longitud: float) -> bool:
        """RF25: el punto está dentro de la zona (el borde cuenta como dentro)."""
        return punto_en_poligono((latitud, longitud), self.limites)
