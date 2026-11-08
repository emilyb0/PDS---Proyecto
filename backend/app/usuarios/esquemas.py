"""Esquemas de usuarios y sesión."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.nucleo.enums import EstadoUsuario, RolUsuario
from app.nucleo.esquemas import Esquema, EsquemaEntrada, FechaHora


class UsuarioSalida(Esquema):
    """Usuario sin la contraseña (nunca se devuelve el hash)."""

    id_usuario: int
    nombre: str
    correo_institucional: str
    rol: RolUsuario
    estado: EstadoUsuario
    fecha_creacion: FechaHora


class UsuarioResumen(Esquema):
    id_usuario: int
    nombre: str


class OperadorOpcion(Esquema):
    id_usuario: int
    nombre: str
    correo_institucional: str


class LoginEntrada(EsquemaEntrada):
    correo: str = Field(min_length=1, max_length=120, examples=["admin@campus.edu.co"])
    contrasena: str = Field(min_length=1, max_length=128, examples=["Admin123*"])


class LoginSalida(BaseModel):
    token: str
    tipo: Literal["bearer"] = "bearer"
    expira: FechaHora
    usuario: UsuarioSalida
    funciones: list[str]
    requisitos_activos: list[str]


class YoSalida(BaseModel):
    usuario: UsuarioSalida
    funciones: list[str]
    requisitos_activos: list[str]


class UsuarioCrear(EsquemaEntrada):
    nombre: str = Field(min_length=1, max_length=100)
    correo_institucional: EmailStr = Field(max_length=120)
    contrasena: str = Field(min_length=8, max_length=128)
    rol: RolUsuario

    @field_validator("correo_institucional")
    @classmethod
    def _minusculas(cls, valor: str) -> str:
        return valor.lower()


class UsuarioEditar(EsquemaEntrada):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    rol: RolUsuario | None = None

    @model_validator(mode="after")
    def _algun_campo(self) -> UsuarioEditar:
        if self.nombre is None and self.rol is None:
            raise ValueError("Indique el nombre o el rol a cambiar.")
        return self
