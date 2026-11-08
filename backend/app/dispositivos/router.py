"""Rutas del inventario de dispositivos del núcleo (RF01, RF04)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dispositivos.esquemas import (
    DispositivoCrear,
    DispositivoDetalle,
    DispositivoSalida,
)
from app.dispositivos.servicio import ServicioDispositivos, obtener_dispositivo
from app.nucleo.dependencias import Administrador, ContenedorDep, Paginacion, Sesion, UsuarioActual
from app.nucleo.enums import EstadoDispositivo, TipoDispositivo
from app.nucleo.esquemas import Pagina


def _servicio(sesion: Sesion, contenedor: ContenedorDep) -> ServicioDispositivos:
    return ServicioDispositivos(sesion, contenedor)


Servicio = Annotated[ServicioDispositivos, Depends(_servicio)]

router = APIRouter(prefix="/api/dispositivos", tags=["Dispositivos"])


@router.get(
    "",
    response_model=Pagina[DispositivoSalida],
    summary="Consultar inventario (RF04)",
    description="RF04, RNF03. Lista de dispositivos con tipo, modelo, número de serie, estado, último nivel de "
    "batería y sensores en falla. Filtros `tipo` y `estado`. Incluye los dados de baja (FUERA_DE_SERVICIO).",
)
async def listar_dispositivos(
    _: UsuarioActual,
    servicio: Servicio,
    paginacion: Paginacion,
    tipo: TipoDispositivo | None = None,
    estado: EstadoDispositivo | None = None,
) -> Pagina[DispositivoSalida]:
    return await servicio.listar(paginacion, tipo, estado)


@router.post(
    "",
    response_model=DispositivoDetalle,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar dispositivo (RF01)",
    description="RF01, RNF01, RNF10. Solo administrador. Tipo, número de serie (único), modelo, capacidad de carga "
    "(robot) o autonomía de vuelo (drone), estado inicial (DISPONIBLE por defecto; también EN_CARGA o "
    "FUERA_DE_SERVICIO) y sensores (si se omiten, los del tipo).",
)
async def registrar_dispositivo(
    datos: DispositivoCrear, administrador: Administrador, servicio: Servicio
) -> DispositivoDetalle:
    dispositivo = await servicio.registrar_dispositivo(datos, administrador)
    return await servicio.detalle(dispositivo)


@router.get(
    "/{id_dispositivo}",
    response_model=DispositivoDetalle,
    summary="Detalle de dispositivo (RF04)",
    description="RF04. Dispositivo con sus sensores, servicio activo y último estado.",
)
async def obtener(id_dispositivo: int, _: UsuarioActual, sesion: Sesion, servicio: Servicio) -> DispositivoDetalle:
    return await servicio.detalle(await obtener_dispositivo(sesion, id_dispositivo))
