"""Rutas de sesión (RF20) y de usuarios (RF18, RNF01). Desactivar (RF19) irá en su módulo (pendiente)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.nucleo.dependencias import Administrador, ContenedorDep, Paginacion, Sesion, UsuarioActual
from app.nucleo.enums import EstadoUsuario, RolUsuario
from app.nucleo.esquemas import Pagina
from app.usuarios.esquemas import (
    LoginEntrada,
    LoginSalida,
    UsuarioCrear,
    UsuarioEditar,
    UsuarioSalida,
    YoSalida,
)
from app.usuarios.servicio import ServicioUsuarios


def _servicio(sesion: Sesion, contenedor: ContenedorDep) -> ServicioUsuarios:
    return ServicioUsuarios(sesion, contenedor)


Servicio = Annotated[ServicioUsuarios, Depends(_servicio)]

router_sesion = APIRouter(prefix="/api/auth", tags=["Sesión"])
router_usuarios = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


@router_sesion.post(
    "/login",
    response_model=LoginSalida,
    summary="Iniciar sesión (RF20)",
    description="RF20. Valida correo y contraseña de un usuario activo y devuelve el token JWT, el usuario y "
    "las funciones de su rol. 401 si los datos son incorrectos; 403 si el usuario está inactivo.",
)
async def iniciar_sesion(datos: LoginEntrada, servicio: Servicio) -> LoginSalida:
    resultado = await servicio.iniciar_sesion(datos.correo, datos.contrasena)
    return LoginSalida(
        token=resultado.token.token,
        expira=resultado.token.expira,
        usuario=UsuarioSalida.model_validate(resultado.usuario),
        funciones=resultado.funciones,
        requisitos_activos=resultado.requisitos_activos,
    )


@router_sesion.get(
    "/yo",
    response_model=YoSalida,
    summary="Usuario actual y funciones de su rol (RF20)",
    description="RF20. Devuelve el usuario autenticado, las funciones de su rol para armar el menú y los "
    "requisitos activos (los de la entrega 1 más los módulos encendidos).",
)
async def yo(usuario: UsuarioActual, servicio: Servicio, contenedor: ContenedorDep) -> YoSalida:
    return YoSalida(
        usuario=UsuarioSalida.model_validate(usuario),
        funciones=servicio.funciones(usuario),
        requisitos_activos=contenedor.requisitos_activos,
    )


@router_usuarios.post(
    "",
    response_model=UsuarioSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar usuario (RF18)",
    description="RF18, RNF01, RNF05. Solo administrador. Registra nombre, correo institucional (único sin "
    "importar mayúsculas), contraseña (mínimo 8 caracteres, se guarda cifrada con Argon2id) y rol.",
)
async def registrar_usuario(datos: UsuarioCrear, administrador: Administrador, servicio: Servicio) -> UsuarioSalida:
    return UsuarioSalida.model_validate(await servicio.registrar_usuario(datos, administrador))


@router_usuarios.get(
    "",
    response_model=Pagina[UsuarioSalida],
    summary="Listar usuarios (RF18)",
    description="RF18. Solo administrador. Filtros `rol` y `estado` (por ejemplo, operadores activos para "
    "elegir el responsable de una reserva).",
)
async def listar_usuarios(
    _: Administrador,
    servicio: Servicio,
    paginacion: Paginacion,
    rol: RolUsuario | None = None,
    estado: EstadoUsuario | None = None,
) -> Pagina[UsuarioSalida]:
    pagina = await servicio.listar_usuarios(paginacion, rol, estado)
    return Pagina[UsuarioSalida](
        items=[UsuarioSalida.model_validate(u) for u in pagina.items],
        total=pagina.total,
        limite=pagina.limite,
        desplazamiento=pagina.desplazamiento,
    )


@router_usuarios.patch(
    "/{id_usuario}",
    response_model=UsuarioSalida,
    summary="Cambiar nombre o rol (RNF01)",
    description="RNF01. Solo administrador. Cambia el nombre o el rol. No se permite quitar el rol al último "
    "administrador activo (409).",
)
async def editar_usuario(
    id_usuario: int, datos: UsuarioEditar, administrador: Administrador, servicio: Servicio
) -> UsuarioSalida:
    return UsuarioSalida.model_validate(await servicio.editar_usuario(id_usuario, datos, administrador))
