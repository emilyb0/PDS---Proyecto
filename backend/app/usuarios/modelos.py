"""Usuario (diagrama: Usuario, Administrador, Operador) → tabla ``usuario``.

Administrador y Operador son valores de ``rol`` en una sola clase (decisión D10).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.nucleo.bd import Base
from app.nucleo.enums import PG_ESTADO_USUARIO, PG_ROL_USUARIO, EstadoUsuario, RolUsuario


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    correo_institucional: Mapped[str] = mapped_column(String(120))
    contrasena_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[RolUsuario] = mapped_column(PG_ROL_USUARIO)
    estado: Mapped[EstadoUsuario] = mapped_column(PG_ESTADO_USUARIO, server_default=EstadoUsuario.ACTIVO.value)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime)

    def esta_activo(self) -> bool:
        return self.estado == EstadoUsuario.ACTIVO

    @property
    def es_administrador(self) -> bool:
        return self.rol == RolUsuario.ADMINISTRADOR

    @property
    def es_operador(self) -> bool:
        return self.rol == RolUsuario.OPERADOR

    def __repr__(self) -> str:
        return f"<Usuario {self.id_usuario} {self.correo_institucional} {self.rol}>"
