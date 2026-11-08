"""Consulta de alertas (RF11, RF16, RF25), del núcleo. La atención (RF27) irá en su módulo (pendiente)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.alertas.esquemas import AlertaSalida, AtencionSalida
from app.alertas.modelos import Alerta, AlertaMantenimiento, AlertaServicio, AtencionAlerta
from app.nucleo.enums import TipoAlerta
from app.nucleo.errores import ErrorNoEncontrado, ErrorValidacion
from app.nucleo.esquemas import Pagina, ParametrosPaginacion
from app.nucleo.paginacion import paginar
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio, Incidencia
from app.usuarios.esquemas import UsuarioResumen


def atencion_salida(atencion: AtencionAlerta) -> AtencionSalida:
    return AtencionSalida(
        id_atencion=atencion.id_atencion,
        id_alerta=atencion.id_alerta,
        operador=UsuarioResumen.model_validate(atencion.operador),
        fecha_hora=atencion.fecha_hora,
        causa_revisada=atencion.causa_revisada,
        observaciones=atencion.observaciones,
    )


async def alertas_a_salida(sesion: AsyncSession, alertas: Sequence[Alerta]) -> list[AlertaSalida]:
    """Arma la salida. Para las de servicio trae en una sola consulta la bitácora, la ubicación y el operador."""
    ids_incidencia = [a.id_incidencia for a in alertas if isinstance(a, AlertaServicio)]
    datos_incidencia = {}
    if ids_incidencia:
        filas = await sesion.execute(
            select(
                Incidencia.id_incidencia,
                Incidencia.id_bitacora,
                Incidencia.latitud,
                Incidencia.longitud,
                Reserva.id_operador,
            )
            .join(BitacoraServicio, BitacoraServicio.id_bitacora == Incidencia.id_bitacora)
            .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
            .where(Incidencia.id_incidencia.in_(ids_incidencia))
        )
        datos_incidencia = {fila.id_incidencia: fila for fila in filas}

    salida = []
    for alerta in alertas:
        comun = {
            "id_alerta": alerta.id_alerta,
            "tipo": alerta.tipo,
            "descripcion": alerta.descripcion,
            "fecha_hora": alerta.fecha_hora,
            "id_dispositivo": alerta.id_dispositivo,
            "numero_serie": alerta.dispositivo.numero_serie,
        }
        if isinstance(alerta, AlertaServicio):
            inc = datos_incidencia.get(alerta.id_incidencia)
            salida.append(
                AlertaSalida(
                    **comun,
                    causa=alerta.causa,
                    id_bitacora=inc.id_bitacora if inc else None,
                    id_incidencia=alerta.id_incidencia,
                    id_operador=inc.id_operador if inc else None,
                    latitud=float(inc.latitud) if inc is not None and inc.latitud is not None else None,
                    longitud=float(inc.longitud) if inc is not None and inc.longitud is not None else None,
                    atendida=alerta.atendida,
                    atencion=atencion_salida(alerta.atencion) if alerta.atencion else None,
                    dias_desde_ultimo=None,
                    horas_desde_ultimo=None,
                )
            )
        else:
            assert isinstance(alerta, AlertaMantenimiento)
            salida.append(
                AlertaSalida(
                    **comun,
                    causa=None,
                    id_bitacora=None,
                    id_incidencia=None,
                    id_operador=None,
                    latitud=None,
                    longitud=None,
                    atendida=None,
                    atencion=None,
                    dias_desde_ultimo=alerta.dias_desde_ultimo,
                    horas_desde_ultimo=float(alerta.horas_desde_ultimo),
                )
            )
    return salida


async def consultar_alertas(
    sesion: AsyncSession,
    paginacion: ParametrosPaginacion,
    *,
    tipo: TipoAlerta | None = None,
    atendida: bool | None = None,
    id_dispositivo: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> Pagina[AlertaSalida]:
    if desde and hasta and desde > hasta:
        raise ErrorValidacion.de_campo("desde", "La fecha inicial no puede ser posterior a la final.")
    consulta = select(Alerta).options(joinedload(Alerta.dispositivo))
    if tipo is not None:
        consulta = consulta.where(Alerta.tipo == tipo)
    if atendida is not None:
        # Solo las alertas de servicio se atienden (decisión D14).
        tiene_atencion = exists().where(AtencionAlerta.id_alerta == Alerta.id_alerta)
        consulta = consulta.where(Alerta.tipo == TipoAlerta.SERVICIO, tiene_atencion if atendida else ~tiene_atencion)
    if id_dispositivo is not None:
        consulta = consulta.where(Alerta.id_dispositivo == id_dispositivo)
    if desde is not None:
        consulta = consulta.where(Alerta.fecha_hora >= desde)
    if hasta is not None:
        consulta = consulta.where(Alerta.fecha_hora < hasta + timedelta(days=1))
    consulta = consulta.order_by(Alerta.fecha_hora.desc(), Alerta.id_alerta.desc())
    pagina = await paginar(sesion, consulta, paginacion, lambda alerta: alerta)
    return Pagina[AlertaSalida](
        items=await alertas_a_salida(sesion, pagina.items),
        total=pagina.total,
        limite=pagina.limite,
        desplazamiento=pagina.desplazamiento,
    )


async def obtener_alerta(sesion: AsyncSession, id_alerta: int) -> AlertaSalida:
    alerta = await sesion.scalar(
        select(Alerta).where(Alerta.id_alerta == id_alerta).options(joinedload(Alerta.dispositivo))
    )
    if alerta is None:
        raise ErrorNoEncontrado(f"No existe la alerta #{id_alerta}.")
    return (await alertas_a_salida(sesion, [alerta]))[0]
