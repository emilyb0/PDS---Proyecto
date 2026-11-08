"""Consultas de bitácoras (RF08) y la foto del monitoreo (RF09)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.alertas.esquemas import AlertaSalida
from app.alertas.modelos import Alerta, AlertaMantenimiento, AlertaServicio, AtencionAlerta
from app.alertas.servicio import alertas_a_salida
from app.dispositivos.esquemas import DispositivoResumen
from app.dispositivos.modelos import Dispositivo
from app.mantenimiento.modelos import Mantenimiento
from app.nucleo.enums import EstadoServicio, TipoAlerta
from app.nucleo.errores import ErrorNoEncontrado, ErrorValidacion
from app.nucleo.esquemas import Pagina, ParametrosPaginacion
from app.nucleo.paginacion import paginar
from app.reservas.esquemas import ReservaSalida, UbicacionResumen
from app.reservas.gestor_reservas import opciones_reserva
from app.reservas.modelos import Reserva
from app.servicios.esquemas import (
    BitacoraDetalle,
    BitacoraSalida,
    DispositivoMonitoreo,
    IncidenciaSalida,
    LecturaSensorSalida,
    MonitoreoSalida,
    PuntoRuta,
    RutaSalida,
    ServicioMonitoreo,
    VideoResumen,
)
from app.servicios.modelos import BitacoraServicio, Incidencia, LecturaSensor, RegistroTelemetria
from app.usuarios.esquemas import UsuarioResumen
from app.videos.modelos import Video

if TYPE_CHECKING:
    from app.contenedor import Contenedor

_NUMERO_INCIDENCIAS = (
    select(func.count(Incidencia.id_incidencia))
    .where(Incidencia.id_bitacora == BitacoraServicio.id_bitacora)
    .correlate(BitacoraServicio)
    .scalar_subquery()
)
_TIENE_VIDEO = exists().where(Video.id_bitacora == BitacoraServicio.id_bitacora)


def _salida(bitacora: BitacoraServicio, reserva: Reserva, incidencias: int, tiene_video: bool) -> dict[str, Any]:
    return {
        "id_bitacora": bitacora.id_bitacora,
        "id_reserva": reserva.id_reserva,
        "estado": bitacora.estado,
        "tipo_servicio": reserva.tipo_servicio,
        "hora_salida": bitacora.hora_salida,
        "hora_regreso": bitacora.hora_regreso,
        "hora_entrega": bitacora.hora_entrega,
        "entregado": bitacora.entregado,
        "dispositivo": DispositivoResumen.de(reserva.dispositivo),
        "operador": UsuarioResumen.model_validate(reserva.operador),
        "numero_incidencias": incidencias,
        "tiene_video": tiene_video,
    }


async def listar_bitacoras(
    sesion: AsyncSession,
    paginacion: ParametrosPaginacion,
    *,
    desde: date | None = None,
    hasta: date | None = None,
    id_dispositivo: int | None = None,
    estado: EstadoServicio | None = None,
) -> Pagina[BitacoraSalida]:
    if desde and hasta and desde > hasta:
        raise ErrorValidacion.de_campo("desde", "La fecha inicial no puede ser posterior a la final.")
    consulta = (
        select(BitacoraServicio, Reserva, _NUMERO_INCIDENCIAS.label("incidencias"), _TIENE_VIDEO.label("video"))
        .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
        .options(joinedload(Reserva.dispositivo), joinedload(Reserva.operador))
    )
    if desde is not None:
        consulta = consulta.where(BitacoraServicio.hora_salida >= desde)
    if hasta is not None:
        consulta = consulta.where(BitacoraServicio.hora_salida < hasta + timedelta(days=1))
    if id_dispositivo is not None:
        consulta = consulta.where(Reserva.id_dispositivo == id_dispositivo)
    if estado is not None:
        consulta = consulta.where(BitacoraServicio.estado == estado)
    consulta = consulta.order_by(BitacoraServicio.hora_salida.desc(), BitacoraServicio.id_bitacora.desc())
    return await paginar(
        sesion,
        consulta,
        paginacion,
        lambda fila: BitacoraSalida(**_salida(fila[0], fila[1], fila[2], fila[3])),
        escalares=False,
    )


async def _bitacora(sesion: AsyncSession, id_bitacora: int) -> BitacoraServicio:
    bitacora = await sesion.scalar(
        select(BitacoraServicio)
        .where(BitacoraServicio.id_bitacora == id_bitacora)
        .options(selectinload(BitacoraServicio.incidencias), selectinload(BitacoraServicio.video))
    )
    if bitacora is None:
        raise ErrorNoEncontrado(f"No existe la bitácora #{id_bitacora}.")
    return bitacora


async def obtener_bitacora(sesion: AsyncSession, id_bitacora: int, *, ver_codigo: bool) -> BitacoraDetalle:
    """RF08: reserva, dispositivo, operador, incidencias (con su alerta, si la generaron) y video."""
    bitacora = await _bitacora(sesion, id_bitacora)
    reserva = await sesion.scalar(
        select(Reserva).where(Reserva.id_reserva == bitacora.id_reserva).options(*opciones_reserva())
    )
    assert reserva is not None
    ids = [i.id_incidencia for i in bitacora.incidencias]
    alertas = {}
    if ids:
        filas = await sesion.execute(
            select(AlertaServicio.id_incidencia, AlertaServicio.id_alerta).where(AlertaServicio.id_incidencia.in_(ids))
        )
        alertas = {fila.id_incidencia: fila.id_alerta for fila in filas}
    video = bitacora.video
    return BitacoraDetalle(
        **_salida(bitacora, reserva, len(bitacora.incidencias), video is not None),
        reserva=ReservaSalida.de(reserva, ver_codigo=ver_codigo),
        horas_uso=bitacora.horas_uso(),
        incidencias=[
            IncidenciaSalida(
                id_incidencia=i.id_incidencia,
                fecha_hora=i.fecha_hora,
                tipo=i.tipo,
                descripcion=i.descripcion,
                latitud=None if i.latitud is None else float(i.latitud),
                longitud=None if i.longitud is None else float(i.longitud),
                id_alerta=alertas.get(i.id_incidencia),
            )
            for i in bitacora.incidencias
        ],
        video=None
        if video is None
        else VideoResumen(
            id_video=video.id_video,
            fecha_grabacion=video.fecha_grabacion,
            duracion_seg=video.duracion_seg,
            eliminado=video.eliminado,
            fecha_eliminacion=video.fecha_eliminacion,
        ),
    )


async def obtener_ruta(sesion: AsyncSession, id_bitacora: int) -> RutaSalida:
    """RF08: puntos de la ruta recorrida, en orden, con la lectura de cada sensor."""
    existe = await sesion.scalar(
        select(BitacoraServicio.id_bitacora).where(BitacoraServicio.id_bitacora == id_bitacora)
    )
    if existe is None:
        raise ErrorNoEncontrado(f"No existe la bitácora #{id_bitacora}.")
    puntos = (
        await sesion.scalars(
            select(RegistroTelemetria)
            .where(RegistroTelemetria.id_bitacora == id_bitacora)
            .options(selectinload(RegistroTelemetria.lecturas).joinedload(LecturaSensor.sensor))
            .order_by(RegistroTelemetria.fecha_hora)
        )
    ).all()
    return RutaSalida(
        id_bitacora=id_bitacora,
        puntos=[
            PuntoRuta(
                fecha_hora=p.fecha_hora,
                latitud=float(p.latitud),
                longitud=float(p.longitud),
                nivel_bateria=p.nivel_bateria,
                estado_servicio=p.estado_servicio,
                sensores=[
                    LecturaSensorSalida(
                        id_sensor=lectura.id_sensor, nombre=lectura.sensor.nombre, estado=lectura.estado
                    )
                    for lectura in sorted(p.lecturas, key=lambda lectura: lectura.id_sensor)
                ],
            )
            for p in puntos
        ],
    )


async def alertas_abiertas(sesion: AsyncSession, limite: int = 200) -> list[AlertaSalida]:
    """Decisión D14: alertas de servicio sin atención y de mantenimiento sin un mantenimiento posterior.

    Una alerta de mantenimiento queda resuelta si después de ella se registró un mantenimiento, o si se cerró uno
    posterior a la referencia con que se calculó (fecha de la alerta menos sus días; decisión F5-10).
    """
    sin_atencion = ~exists().where(AtencionAlerta.id_alerta == Alerta.id_alerta)
    tabla = AlertaMantenimiento.__table__
    dias = select(tabla.c.dias_desde_ultimo).where(tabla.c.id_alerta == Alerta.id_alerta).scalar_subquery()
    referencia = cast(Alerta.fecha_hora, Date) - dias
    sin_mantenimiento = ~exists().where(
        Mantenimiento.id_dispositivo == Alerta.id_dispositivo,
        or_(Mantenimiento.fecha_inicio >= cast(Alerta.fecha_hora, Date), Mantenimiento.fecha_fin > referencia),
    )
    alertas = (
        await sesion.scalars(
            select(Alerta)
            .options(joinedload(Alerta.dispositivo))
            .where(
                or_(
                    (Alerta.tipo == TipoAlerta.SERVICIO) & sin_atencion,
                    (Alerta.tipo == TipoAlerta.MANTENIMIENTO) & sin_mantenimiento,
                )
            )
            .order_by(Alerta.fecha_hora.desc(), Alerta.id_alerta.desc())
            .limit(limite)
        )
    ).all()
    return await alertas_a_salida(sesion, alertas)


async def foto_monitoreo(sesion: AsyncSession, contenedor: Contenedor) -> MonitoreoSalida:
    """RF09: todos los dispositivos que no están dados de baja, con su última lectura y su servicio activo."""
    dispositivos = (
        await sesion.scalars(
            select(Dispositivo).where(Dispositivo.fecha_baja.is_(None)).order_by(Dispositivo.numero_serie)
        )
    ).all()
    filas = (
        await sesion.execute(
            select(BitacoraServicio, Reserva)
            .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
            .where(BitacoraServicio.estado != EstadoServicio.FINALIZADO)
            .options(joinedload(Reserva.destino), joinedload(Reserva.operador))
        )
    ).all()
    servicios = {
        reserva.id_dispositivo: ServicioMonitoreo(
            id_bitacora=bitacora.id_bitacora,
            id_reserva=reserva.id_reserva,
            tipo_servicio=reserva.tipo_servicio,
            estado=bitacora.estado,
            hora_salida=bitacora.hora_salida,
            fin_estimado=reserva.fin,
            destino=UbicacionResumen(id_ubicacion=reserva.destino.id_ubicacion, nombre=reserva.destino.nombre),
            operador=UsuarioResumen.model_validate(reserva.operador),
        )
        for bitacora, reserva in filas
    }
    return MonitoreoSalida(
        generado=contenedor.reloj.ahora(),
        intervalo_seg=contenedor.config.intervalo_monitoreo_seg,
        dispositivos=[
            DispositivoMonitoreo(
                id_dispositivo=d.id_dispositivo,
                numero_serie=d.numero_serie,
                tipo=d.tipo,
                modelo=d.modelo,
                estado=d.estado,
                telemetria=contenedor.monitor.ultima_telemetria(d.id_dispositivo),
                servicio=servicios.get(d.id_dispositivo),
            )
            for d in dispositivos
        ],
        alertas_abiertas=await alertas_abiertas(sesion),
    )
