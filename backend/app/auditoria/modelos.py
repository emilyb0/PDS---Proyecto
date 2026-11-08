"""RegistroAuditoria → tabla ``registro_auditoria`` (RNF09)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.nucleo.bd import Base
from app.nucleo.enums import PG_ACCION_AUDITORIA, AccionAuditoria
from app.usuarios.modelos import Usuario


class RegistroAuditoria(Base):
    __tablename__ = "registro_auditoria"

    id_auditoria: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id_usuario"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    accion: Mapped[AccionAuditoria] = mapped_column(PG_ACCION_AUDITORIA)
    entidad: Mapped[str] = mapped_column(String(50))
    id_entidad: Mapped[int] = mapped_column(Integer)

    usuario: Mapped[Usuario] = relationship(lazy="raise")
