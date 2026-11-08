"""Casos de uso de usuarios y sesión del núcleo (RF18, RF20, RNF01, RNF05).

``registrar_usuario`` del Administrador del diagrama vive aquí; ``desactivar_usuario`` (RF19) irá en su módulo
(pendiente), que puede reutilizar ``obtener_usuario`` y ``exigir_otro_administrador_activo``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auditoria.servicio import registrar_auditoria
from app.contenedor import Contenedor
from app.nucleo.enums import AccionAuditoria, EstadoUsuario, RolUsuario
from app.nucleo.errores import (
    ErrorDuplicado,
    ErrorNoAutenticado,
    ErrorNoEncontrado,
    ErrorReglaNegocio,
    ErrorSinPermiso,
    ErrorValidacion,
)
from app.nucleo.esquemas import Pagina, ParametrosPaginacion
from app.nucleo.paginacion import paginar
from app.nucleo.seguridad import TokenEmitido
from app.usuarios.esquemas import UsuarioCrear, UsuarioEditar
from app.usuarios.modelos import Usuario
from app.usuarios.permisos import funciones_de

MENSAJE_LOGIN_INCORRECTO = "Correo o contraseña incorrectos."


@dataclass
class SesionIniciada:
    token: TokenEmitido
    usuario: Usuario
    funciones: list[str]
    requisitos_activos: list[str]


async def obtener_usuario(sesion: AsyncSession, id_usuario: int) -> Usuario:
    usuario = await sesion.get(Usuario, id_usuario)
    if usuario is None:
        raise ErrorNoEncontrado(f"No existe el usuario #{id_usuario}.")
    return usuario


async def exigir_otro_administrador_activo(sesion: AsyncSession, usuario: Usuario) -> None:
    """El sistema no puede quedar sin administradores activos (al quitar el rol o desactivar).

    Bloquea las filas de los administradores activos siempre en el mismo orden (por id), así dos
    cambios simultáneos no se cruzan, y relee el usuario ya con el bloqueo puesto.
    """
    consulta = (
        select(Usuario.id_usuario)
        .where(Usuario.rol == RolUsuario.ADMINISTRADOR, Usuario.estado == EstadoUsuario.ACTIVO)
        .order_by(Usuario.id_usuario)
        .with_for_update()
    )
    activos = set((await sesion.scalars(consulta)).all())
    await sesion.refresh(usuario)
    if usuario.rol != RolUsuario.ADMINISTRADOR or not usuario.esta_activo():
        return
    if activos - {usuario.id_usuario}:
        return
    raise ErrorReglaNegocio("Debe quedar al menos un administrador activo.")


class ServicioUsuarios:
    def __init__(self, sesion: AsyncSession, contenedor: Contenedor) -> None:
        self.sesion = sesion
        self.c = contenedor

    # ------------------------------------------------------------------ RF20

    async def iniciar_sesion(self, correo: str, contrasena: str) -> SesionIniciada:
        """Mismo mensaje para correo inexistente y contraseña errada; 403 si la contraseña es correcta
        pero el usuario está inactivo (especificación 7.1)."""
        usuario = await self._por_correo(correo)
        if usuario is None:
            await asyncio.to_thread(self.c.cifrador.verificar_ficticio, contrasena)
            raise ErrorNoAutenticado(MENSAJE_LOGIN_INCORRECTO)
        valida = await asyncio.to_thread(self.c.cifrador.verificar, usuario.contrasena_hash, contrasena)
        if not valida:
            raise ErrorNoAutenticado(MENSAJE_LOGIN_INCORRECTO)
        if not usuario.esta_activo():
            raise ErrorSinPermiso("Usuario inactivo.")
        token = self.c.tokens.emitir(usuario.id_usuario, usuario.rol.value)
        return SesionIniciada(token, usuario, self.funciones(usuario), self.c.requisitos_activos)

    def funciones(self, usuario: Usuario) -> list[str]:
        return funciones_de(usuario.rol, self.c.config.modo_demo, self.c.extensiones)

    # ------------------------------------------------------------------ RF18

    async def registrar_usuario(self, datos: UsuarioCrear, administrador: Usuario) -> Usuario:
        correo = datos.correo_institucional.lower()
        dominio = self.c.config.dominio_correo_institucional
        if dominio and not correo.endswith("@" + dominio.lower()):
            raise ErrorValidacion.de_campo(
                "correo_institucional", f"El correo debe ser del dominio institucional @{dominio}."
            )
        if await self._por_correo(correo) is not None:
            raise ErrorDuplicado("Ya existe un usuario con ese correo institucional.")
        contrasena_hash = await asyncio.to_thread(self.c.cifrador.cifrar, datos.contrasena)
        usuario = Usuario(
            nombre=datos.nombre,
            correo_institucional=correo,
            contrasena_hash=contrasena_hash,
            rol=datos.rol,
            estado=EstadoUsuario.ACTIVO,
            fecha_creacion=self.c.reloj.ahora(),
        )
        self.sesion.add(usuario)
        await self.sesion.flush()
        registrar_auditoria(
            self.sesion, self.c.reloj, administrador, AccionAuditoria.CREAR, "usuario", usuario.id_usuario
        )
        await self.sesion.commit()
        return usuario

    async def listar_usuarios(
        self,
        paginacion: ParametrosPaginacion,
        rol: RolUsuario | None = None,
        estado: EstadoUsuario | None = None,
    ) -> Pagina[Usuario]:
        consulta = select(Usuario)
        if rol is not None:
            consulta = consulta.where(Usuario.rol == rol)
        if estado is not None:
            consulta = consulta.where(Usuario.estado == estado)
        consulta = consulta.order_by(Usuario.nombre, Usuario.id_usuario)
        return await paginar(self.sesion, consulta, paginacion, lambda u: u)

    # ------------------------------------------------------------------ RNF01: cambiar nombre o rol

    async def editar_usuario(self, id_usuario: int, datos: UsuarioEditar, administrador: Usuario) -> Usuario:
        usuario = await obtener_usuario(self.sesion, id_usuario)
        if datos.rol is not None and datos.rol != usuario.rol:
            if usuario.rol == RolUsuario.ADMINISTRADOR:
                await exigir_otro_administrador_activo(self.sesion, usuario)
            usuario.rol = datos.rol
        if datos.nombre is not None:
            usuario.nombre = datos.nombre
        registrar_auditoria(
            self.sesion, self.c.reloj, administrador, AccionAuditoria.EDITAR, "usuario", usuario.id_usuario
        )
        await self.sesion.commit()
        return usuario

    # ------------------------------------------------------------------ apoyo

    async def _por_correo(self, correo: str) -> Usuario | None:
        consulta = select(Usuario).where(func.lower(Usuario.correo_institucional) == correo.strip().lower())
        return await self.sesion.scalar(consulta)
