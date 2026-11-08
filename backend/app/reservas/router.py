"""Rutas de reservas del núcleo (RF05–RF07).

Las rutas con id usan el convertidor ``:int``, así ``/api/reservas/sugerencia`` (módulo RF22) no choca con
``/api/reservas/{id_reserva}``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.nucleo.dependencias import Administrador, ContenedorDep, Paginacion, Sesion, UsuarioActual
from app.nucleo.enums import EstadoReserva
from app.nucleo.esquemas import Pagina
from app.reservas.esquemas import ReservaCrear, ReservaSalida
from app.reservas.gestor_reservas import GestorReservas


def _gestor(sesion: Sesion, contenedor: ContenedorDep) -> GestorReservas:
    return GestorReservas(sesion, contenedor)


Gestor = Annotated[GestorReservas, Depends(_gestor)]

router = APIRouter(prefix="/api/reservas", tags=["Reservas"])


@router.post(
    "",
    response_model=ReservaSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear reserva (RF05, RF06, RF07)",
    description="RF05, RF06, RF07, RNF01. Solo administrador. Valida en este orden y se detiene en la primera "
    "falla: tipo de dispositivo para el servicio (409 `TIPO_DISPOSITIVO_INCORRECTO`), estado del dispositivo "
    "(409 `DISPOSITIVO_NO_APTO`), cruce de horario con la reserva en conflicto (409 `CRUCE_HORARIO`), batería y "
    "sensores consultados al dispositivo en ese momento (409 `DISPOSITIVO_NO_APTO` con `motivos`) y las "
    "validaciones de los módulos activos, si los hay (por ejemplo, el clima de RF23, pendiente). Si el dispositivo "
    "es un robot, devuelve el código de entrega de 4 dígitos.",
)
async def crear_reserva(datos: ReservaCrear, administrador: Administrador, gestor: Gestor) -> ReservaSalida:
    reserva, advertencias = await gestor.crear_reserva(datos, administrador)
    return ReservaSalida.de(reserva, ver_codigo=True, advertencias=advertencias)


@router.get(
    "",
    response_model=Pagina[ReservaSalida],
    summary="Listar reservas (RF05)",
    description="RF05, RNF03. Reservas ordenadas por inicio. Filtros `fecha`, `estado` e `id_dispositivo`. "
    "El código de entrega solo lo ve el administrador.",
)
async def listar_reservas(
    usuario: UsuarioActual,
    gestor: Gestor,
    paginacion: Paginacion,
    fecha: date | None = None,
    estado: EstadoReserva | None = None,
    id_dispositivo: int | None = None,
) -> Pagina[ReservaSalida]:
    pagina = await gestor.listar(paginacion, fecha=fecha, estado=estado, id_dispositivo=id_dispositivo)
    return Pagina[ReservaSalida](
        items=[ReservaSalida.de(r, ver_codigo=usuario.es_administrador) for r in pagina.items],
        total=pagina.total,
        limite=pagina.limite,
        desplazamiento=pagina.desplazamiento,
    )


@router.get(
    "/{id_reserva:int}",
    response_model=ReservaSalida,
    summary="Detalle de reserva (RF05)",
    description="RF05. Una reserva con su dispositivo, operador, origen y destino. El código de entrega solo lo ve "
    "el administrador.",
)
async def detalle_reserva(id_reserva: int, usuario: UsuarioActual, gestor: Gestor) -> ReservaSalida:
    return ReservaSalida.de(await gestor.obtener(id_reserva), ver_codigo=usuario.es_administrador)
