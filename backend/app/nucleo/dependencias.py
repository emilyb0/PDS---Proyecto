"""Dependencias de FastAPI: sesión, contenedor, usuario autenticado y roles (RF20, RNF01, RF19)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.contenedor import Contenedor
from app.nucleo.bd import obtener_sesion
from app.nucleo.errores import ErrorNoAutenticado, ErrorNoEncontrado, ErrorSinPermiso
from app.nucleo.esquemas import ParametrosPaginacion
from app.usuarios.modelos import Usuario


def obtener_contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
ContenedorDep = Annotated[Contenedor, Depends(obtener_contenedor)]
Paginacion = Annotated[ParametrosPaginacion, Query()]

_esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT obtenido en POST /api/auth/login")


async def autenticar_token(token: str, contenedor: Contenedor, sesion: AsyncSession) -> Usuario:
    """Valida el token y que el usuario exista y siga activo. El estado se revisa en cada petición (RF19)."""
    id_usuario = contenedor.tokens.validar(token)
    usuario = await sesion.get(Usuario, id_usuario)
    if usuario is None:
        raise ErrorNoAutenticado("El usuario del token no existe.")
    if not usuario.esta_activo():
        raise ErrorNoAutenticado("Usuario inactivo.")
    return usuario


async def usuario_actual(
    request: Request,
    sesion: Sesion,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema_bearer)],
) -> Usuario:
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise ErrorNoAutenticado("Falta el token de acceso.")
    return await autenticar_token(credenciales.credentials, obtener_contenedor(request), sesion)


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


async def solo_administrador(usuario: UsuarioActual) -> Usuario:
    """RNF01: las funciones de administrador responden 403 al operador."""
    if not usuario.es_administrador:
        raise ErrorSinPermiso("Esta acción es solo para administradores.")
    return usuario


Administrador = Annotated[Usuario, Depends(solo_administrador)]


def requiere_modo_demo(request: Request) -> None:
    """Los controles de demo existen solo con ``MODO_DEMO=true``; si no, responden 404 como si no existieran."""
    if not obtener_contenedor(request).config.modo_demo:
        raise ErrorNoEncontrado("No se encontró el recurso.")


ModoDemo = Annotated[None, Depends(requiere_modo_demo)]
