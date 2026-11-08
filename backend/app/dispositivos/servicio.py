"""Casos de uso del inventario del núcleo: registrar y consultar (RF01, RF04, RNF10).

Editar (RF02) y dar de baja (RF03) serán módulos (pendientes) y pueden reutilizar ``obtener_dispositivo``,
``reservas_del_dispositivo``, ``advertencia_reservas_programadas`` y ``ServicioDispositivos.detalle``.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auditoria.servicio import registrar_auditoria
from app.contenedor import Contenedor
from app.dispositivos.esquemas import (
    DispositivoCrear,
    DispositivoDetalle,
    DispositivoSalida,
    SensorSalida,
    ServicioActivo,
    TelemetriaResumen,
)
from app.dispositivos.modelos import CLASE_POR_TIPO, SENSORES_POR_TIPO, Dispositivo, Sensor
from app.nucleo.enums import (
    AccionAuditoria,
    EstadoDispositivo,
    EstadoReserva,
    EstadoServicio,
    TipoDispositivo,
)
from app.nucleo.errores import (
    ErrorDuplicado,
    ErrorNoEncontrado,
)
from app.nucleo.esquemas import Advertencia, Pagina, ParametrosPaginacion
from app.nucleo.paginacion import paginar
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio, RegistroTelemetria
from app.usuarios.modelos import Usuario

PENDIENTES = (EstadoReserva.PROGRAMADA, EstadoReserva.EN_CURSO)


def a_decimal(valor: float | None) -> Decimal | None:
    return None if valor is None else Decimal(str(round(valor, 2)))


async def obtener_dispositivo(sesion: AsyncSession, id_dispositivo: int, *, bloquear: bool = False) -> Dispositivo:
    """Carga el dispositivo (con sus sensores). ``bloquear`` toma la fila con FOR UPDATE para cambiar su estado."""
    dispositivo = await sesion.get(
        Dispositivo, id_dispositivo, with_for_update=bloquear or None, populate_existing=bloquear
    )
    if dispositivo is None:
        raise ErrorNoEncontrado(f"No existe el dispositivo #{id_dispositivo}.")
    return dispositivo


async def reservas_del_dispositivo(
    sesion: AsyncSession, id_dispositivo: int, estados: Sequence[EstadoReserva]
) -> list[int]:
    consulta = (
        select(Reserva.id_reserva)
        .where(Reserva.id_dispositivo == id_dispositivo, Reserva.estado.in_(estados))
        .order_by(Reserva.fecha, Reserva.hora_inicio)
    )
    return list((await sesion.scalars(consulta)).all())


def advertencia_reservas_programadas(reservas: list[int], motivo: str) -> Advertencia:
    return Advertencia(
        codigo="RESERVAS_PROGRAMADAS",
        mensaje=f"El dispositivo tiene {len(reservas)} reserva(s) programada(s) que no se iniciarán {motivo}.",
        detalles={"reservas": reservas},
    )


class ServicioDispositivos:
    def __init__(self, sesion: AsyncSession, contenedor: Contenedor) -> None:
        self.sesion = sesion
        self.c = contenedor

    # ------------------------------------------------------------------ RF01

    async def registrar_dispositivo(self, datos: DispositivoCrear, administrador: Usuario) -> Dispositivo:
        existente = await self.sesion.scalar(
            select(Dispositivo.id_dispositivo).where(Dispositivo.numero_serie == datos.numero_serie)
        )
        if existente is not None:
            raise ErrorDuplicado(f"Ya existe un dispositivo con el número de serie {datos.numero_serie}.")
        clase = CLASE_POR_TIPO[datos.tipo]
        nombres = datos.sensores or SENSORES_POR_TIPO[datos.tipo]
        dispositivo = clase(
            numero_serie=datos.numero_serie,
            modelo=datos.modelo,
            estado=datos.estado,
            nivel_bateria=100,
            horas_uso_desde_mant=Decimal("0"),
            capacidad_carga_kg=a_decimal(datos.capacidad_carga_kg),
            autonomia_vuelo_min=datos.autonomia_vuelo_min,
            fecha_registro=self.c.reloj.hoy(),
            sensores=[Sensor(nombre=nombre) for nombre in nombres],
        )
        self.sesion.add(dispositivo)
        await self.sesion.flush()
        registrar_auditoria(
            self.sesion, self.c.reloj, administrador, AccionAuditoria.CREAR, "dispositivo", dispositivo.id_dispositivo
        )
        await self.sesion.commit()
        return dispositivo

    # ------------------------------------------------------------------ RF04

    async def listar(
        self,
        paginacion: ParametrosPaginacion,
        tipo: TipoDispositivo | None = None,
        estado: EstadoDispositivo | None = None,
    ) -> Pagina[DispositivoSalida]:
        """Inventario filtrable por tipo y estado. Incluye los dados de baja (salen FUERA_DE_SERVICIO)."""
        consulta = select(Dispositivo)
        if tipo is not None:
            consulta = consulta.where(Dispositivo.tipo == tipo)
        if estado is not None:
            consulta = consulta.where(Dispositivo.estado == estado)
        consulta = consulta.order_by(Dispositivo.tipo, Dispositivo.numero_serie)
        return await paginar(self.sesion, consulta, paginacion, DispositivoSalida.de)

    async def detalle(self, dispositivo: Dispositivo, advertencias: Sequence[Advertencia] = ()) -> DispositivoDetalle:
        """Dispositivo con sensores, servicio activo y última telemetría guardada."""
        servicio = (
            await self.sesion.execute(
                select(BitacoraServicio.id_bitacora, BitacoraServicio.id_reserva, BitacoraServicio.estado)
                .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
                .where(
                    Reserva.id_dispositivo == dispositivo.id_dispositivo,
                    BitacoraServicio.estado != EstadoServicio.FINALIZADO,
                )
            )
        ).first()
        punto = await self.sesion.scalar(
            select(RegistroTelemetria)
            .join(BitacoraServicio, BitacoraServicio.id_bitacora == RegistroTelemetria.id_bitacora)
            .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
            .where(Reserva.id_dispositivo == dispositivo.id_dispositivo)
            .order_by(RegistroTelemetria.fecha_hora.desc())
            .limit(1)
        )
        return DispositivoDetalle(
            **DispositivoSalida.de(dispositivo).model_dump(),
            sensores=[
                SensorSalida(id_sensor=s.id_sensor, nombre=s.nombre, estado=s.estado) for s in dispositivo.sensores
            ],
            servicio_activo=None
            if servicio is None
            else ServicioActivo(
                id_bitacora=servicio.id_bitacora, id_reserva=servicio.id_reserva, estado=servicio.estado.value
            ),
            ultima_telemetria=None
            if punto is None
            else TelemetriaResumen(
                fecha_hora=punto.fecha_hora,
                latitud=float(punto.latitud),
                longitud=float(punto.longitud),
                nivel_bateria=punto.nivel_bateria,
                estado_servicio=punto.estado_servicio,
            ),
            advertencias=list(advertencias),
        )
