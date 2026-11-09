"""``GestorReservas`` del núcleo: crear reservas (RF05) validando cruce (RF06) y batería y sensores (RF07).

Las validaciones van en el orden del diagrama de secuencia (pasos 12–28) y se detienen en la primera que falla
(especificación 7.4):

1. tipo de dispositivo correcto para el servicio;
2. dispositivo no dado de baja, ni en mantenimiento, ni fuera de servicio;
3. RF06: sin cruce con otra reserva PROGRAMADA o EN_CURSO del dispositivo;
4. RF07: batería ≥ mínimo y sensores sin falla, consultados al dispositivo en ese momento;
5. validadores de los módulos (``Extensiones.validadores_reserva``; por ejemplo, el clima de RF23);
6. se guarda la reserva PROGRAMADA (con código de entrega si es robot) y se audita.

Los métodos ``cancelar_reserva``, ``reprogramar_reserva``, ``sugerir_dispositivo`` y ``validar_clima`` del diagrama
irán en los módulos RF21, RF22 y RF23 (pendientes; decisión M-9), que pueden reutilizar estas validaciones.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.auditoria.servicio import registrar_auditoria
from app.contenedor import Contenedor
from app.dispositivos.modelos import Dispositivo
from app.dispositivos.servicio import obtener_dispositivo
from app.dominio.reglas import NOMBRE_SERVICIO, tipo_requerido
from app.integraciones.dispositivo.interfaz import ErrorDispositivo
from app.nucleo.enums import (
    AccionAuditoria,
    EstadoReserva,
    RolUsuario,
    TipoDispositivo,
    TipoServicio,
)
from app.nucleo.errores import (
    ErrorCruceHorario,
    ErrorDispositivoNoApto,
    ErrorNoEncontrado,
    ErrorServicioNoDisponible,
    ErrorTipoDispositivoIncorrecto,
    ErrorValidacion,
    es_error_bd,
)
from app.nucleo.esquemas import Advertencia, Pagina, ParametrosPaginacion
from app.nucleo.paginacion import paginar
from app.reservas.esquemas import ReservaCrear
from app.reservas.modelos import Reserva
from app.ubicaciones.modelos import Ubicacion
from app.usuarios.modelos import Usuario

registro = logging.getLogger(__name__)

ACTIVAS = (EstadoReserva.PROGRAMADA, EstadoReserva.EN_CURSO)


@dataclass
class ContextoReserva:
    """Lo que recibe cada validador de los módulos (``Extensiones.validadores_reserva``)."""

    sesion: AsyncSession
    contenedor: Contenedor
    dispositivo: Dispositivo
    tipo_servicio: TipoServicio
    inicio: datetime
    fin: datetime
    origen: Ubicacion
    destino: Ubicacion
    id_reserva: int | None = None  # se llena al reprogramar


def opciones_reserva() -> list:
    """Relaciones que necesita ``ReservaSalida``."""
    return [
        joinedload(Reserva.origen),
        joinedload(Reserva.destino),
        joinedload(Reserva.dispositivo),
        joinedload(Reserva.operador),
        joinedload(Reserva.administrador),
        selectinload(Reserva.bitacora),
    ]


def _hhmm(momento: datetime) -> str:
    return momento.strftime("%H:%M")


class GestorReservas:
    def __init__(self, sesion: AsyncSession, contenedor: Contenedor) -> None:
        self.sesion = sesion
        self.c = contenedor

    # ================================================================== validaciones de entrada (422)

    async def validar_entrada(self, datos: ReservaCrear, inicio: datetime) -> tuple[Ubicacion, Ubicacion, Usuario]:
        """Revisa la fecha, el origen, el destino y el operador, y responde **todos** los campos con error juntos.

        Se acepta el minuto en curso (decisión D12).
        """
        campos: list[tuple[str, str]] = []
        if inicio < self.c.reloj.ahora().replace(second=0, microsecond=0):
            campos.append(("hora_inicio", "La fecha y hora de inicio no pueden estar en el pasado."))
        origen = await self.sesion.get(Ubicacion, datos.id_origen)
        if origen is None:
            campos.append(("id_origen", "La ubicación de origen no existe."))
        destino = await self.sesion.get(Ubicacion, datos.id_destino)
        if destino is None:
            campos.append(("id_destino", "La ubicación de destino no existe."))
        elif datos.id_origen == datos.id_destino:
            campos.append(("id_destino", "El origen y el destino deben ser distintos."))
        operador = await self.sesion.get(Usuario, datos.id_operador)
        if operador is None or operador.rol != RolUsuario.OPERADOR or not operador.esta_activo():
            campos.append(("id_operador", "El responsable debe ser un operador activo."))
        if campos:
            raise ErrorValidacion.de_campos(campos)
        assert origen is not None and destino is not None and operador is not None
        return origen, destino, operador

    # ================================================================== pasos 1 a 5

    def validar_tipo(self, dispositivo: Dispositivo, tipo_servicio: TipoServicio) -> None:
        """Paso 1: entregas con robot, grabación con drone."""
        requerido = tipo_requerido(tipo_servicio)
        if dispositivo.tipo != requerido:
            nombre = "un robot" if requerido == TipoDispositivo.ROBOT else "un drone"
            raise ErrorTipoDispositivoIncorrecto(
                f"El servicio de {NOMBRE_SERVICIO[tipo_servicio]} requiere {nombre}; "
                f"{dispositivo.numero_serie} no lo es.",
                {"tipo_requerido": requerido.value},
            )

    def motivos_estado(self, dispositivo: Dispositivo) -> list[str]:
        return dispositivo.motivos_estado()

    def validar_estado(self, dispositivo: Dispositivo) -> None:
        """Paso 2: un dispositivo dado de baja, en mantenimiento o fuera de servicio no se asigna."""
        if motivos := self.motivos_estado(dispositivo):
            raise ErrorDispositivoNoApto(motivos[0] + ".", {"motivos": motivos})

    async def buscar_cruce(
        self, id_dispositivo: int, inicio: datetime, fin: datetime, excluir: int | None = None
    ) -> Reserva | None:
        """RF06: la reserva PROGRAMADA o EN_CURSO del dispositivo que se cruza con [inicio, fin), si existe."""
        consulta = (
            select(Reserva)
            .where(
                Reserva.id_dispositivo == id_dispositivo,
                Reserva.estado.in_(ACTIVAS),
                Reserva.horario.op("&&")(func.tsrange(inicio, fin, "[)")),
            )
            .options(joinedload(Reserva.operador), joinedload(Reserva.dispositivo))
            .order_by(Reserva.fecha, Reserva.hora_inicio)
            .limit(1)
        )
        if excluir is not None:
            consulta = consulta.where(Reserva.id_reserva != excluir)
        return await self.sesion.scalar(consulta)

    @staticmethod
    def error_cruce(conflicto: Reserva) -> ErrorCruceHorario:
        return ErrorCruceHorario(
            f"El dispositivo {conflicto.dispositivo.numero_serie} ya tiene la reserva #{conflicto.id_reserva} "
            f"el {conflicto.fecha:%d/%m/%Y} de {_hhmm(conflicto.inicio)} a {_hhmm(conflicto.fin)}.",
            {
                "reserva_en_conflicto": {
                    "id_reserva": conflicto.id_reserva,
                    "fecha": conflicto.fecha.isoformat(),
                    "hora_inicio": _hhmm(conflicto.inicio),
                    "hora_fin": _hhmm(conflicto.fin),
                    "tipo_servicio": conflicto.tipo_servicio.value,
                    "estado": conflicto.estado.value,
                    "operador": {"id_usuario": conflicto.operador.id_usuario, "nombre": conflicto.operador.nombre},
                }
            },
        )

    async def validar_cruce_horario(
        self, dispositivo: Dispositivo, inicio: datetime, fin: datetime, excluir: int | None = None
    ) -> None:
        """Paso 3 (RF06): rechaza mostrando la reserva en conflicto. Las reservas contiguas no se cruzan."""
        conflicto = await self.buscar_cruce(dispositivo.id_dispositivo, inicio, fin, excluir)
        if conflicto is not None:
            raise self.error_cruce(conflicto)

    async def consultar_bateria_y_sensores(self, dispositivo: Dispositivo) -> list[str]:
        """RF07: consulta al dispositivo **en ese momento** y devuelve los motivos de rechazo (vacío = apto).

        De paso actualiza ``nivel_bateria`` y ``sensor.estado`` y lo confirma en su propia transacción: es la
        lectura más reciente y se guarda aunque la reserva se rechace.
        """
        try:
            telemetria = await self.c.api_dispositivo.obtener_telemetria(dispositivo.numero_serie)
        except ErrorDispositivo as error:
            raise ErrorServicioNoDisponible(
                f"No se pudo consultar la batería y los sensores de {dispositivo.numero_serie}: {error}"
            ) from error
        dispositivo.actualizar_lectura(telemetria.nivel_bateria, telemetria.sensores)
        await self.sesion.commit()
        return dispositivo.motivos_no_apto(self.c.config.bateria_minima_asignacion)

    async def validar_bateria_y_sensores(self, dispositivo: Dispositivo) -> None:
        """Paso 4 (RF07): batería menor al mínimo o algún sensor en falla rechaza, indicando el motivo."""
        if motivos := await self.consultar_bateria_y_sensores(dispositivo):
            raise ErrorDispositivoNoApto(
                f"El dispositivo {dispositivo.numero_serie} no está apto: {'; '.join(motivos)}.",
                {"motivos": motivos},
            )

    async def ejecutar_validadores_extra(self, contexto: ContextoReserva) -> list[Advertencia]:
        """Paso 5: validaciones de los módulos activos (por ejemplo, el clima de RF23)."""
        advertencias: list[Advertencia] = []
        for validador in self.c.extensiones.validadores_reserva:
            advertencias.extend(await validador(contexto) or [])
        return advertencias

    async def bloquear_dispositivo(self, dispositivo: Dispositivo) -> None:
        """Toma la fila del dispositivo con FOR SHARE antes de guardar (decisión F2-5).

        Varias reservas del mismo dispositivo pueden avanzar a la vez (el EXCLUDE decide si se cruzan), pero una
        baja simultánea (FOR UPDATE) queda en orden. Después del bloqueo se vuelve a revisar el estado.
        """
        await self.sesion.execute(
            select(Dispositivo)
            .where(Dispositivo.id_dispositivo == dispositivo.id_dispositivo)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        self.validar_estado(dispositivo)

    async def guardar_con_exclusion(self, reserva: Reserva, inicio: datetime, fin: datetime) -> None:
        """Escribe la reserva. Si la base la rechaza por ``ex_reserva_cruce`` (23P01), responde como el paso 3."""
        try:
            await self.sesion.flush()
        except IntegrityError as error:
            if not es_error_bd(error, "23P01"):
                raise
            await self.sesion.rollback()
            conflicto = await self.buscar_cruce(reserva.id_dispositivo, inicio, fin, excluir=reserva.id_reserva)
            if conflicto is None:
                raise ErrorCruceHorario("El horario se cruza con otra reserva activa del dispositivo.") from error
            raise self.error_cruce(conflicto) from error

    # ================================================================== RF05: crear

    async def crear_reserva(self, datos: ReservaCrear, administrador: Usuario) -> tuple[Reserva, list[Advertencia]]:
        inicio = datetime.combine(datos.fecha, datos.hora_inicio)
        fin = inicio + timedelta(minutes=datos.duracion_estimada_min)
        origen, destino, operador = await self.validar_entrada(datos, inicio)
        dispositivo = await obtener_dispositivo(self.sesion, datos.id_dispositivo)

        self.validar_tipo(dispositivo, datos.tipo_servicio)
        self.validar_estado(dispositivo)
        await self.validar_cruce_horario(dispositivo, inicio, fin)
        await self.validar_bateria_y_sensores(dispositivo)
        advertencias = await self.ejecutar_validadores_extra(
            ContextoReserva(self.sesion, self.c, dispositivo, datos.tipo_servicio, inicio, fin, origen, destino)
        )

        await self.bloquear_dispositivo(dispositivo)
        reserva = Reserva(
            id_administrador=administrador.id_usuario,
            id_operador=operador.id_usuario,
            id_dispositivo=dispositivo.id_dispositivo,
            id_origen=origen.id_ubicacion,
            id_destino=destino.id_ubicacion,
            tipo_servicio=datos.tipo_servicio,
            fecha=datos.fecha,
            hora_inicio=datos.hora_inicio,
            duracion_estimada_min=datos.duracion_estimada_min,
            estado=EstadoReserva.PROGRAMADA,
            # El trigger exige el código en los robots (decisión M-6); RF24 lo usa para confirmar la entrega.
            codigo_entrega=Reserva.generar_codigo_entrega() if dispositivo.tipo == TipoDispositivo.ROBOT else None,
            fecha_creacion=self.c.reloj.ahora(),
        )
        self.sesion.add(reserva)
        await self.guardar_con_exclusion(reserva, inicio, fin)
        registrar_auditoria(
            self.sesion, self.c.reloj, administrador, AccionAuditoria.CREAR, "reserva", reserva.id_reserva
        )
        await self.sesion.commit()
        return await self.obtener(reserva.id_reserva), advertencias

    # ================================================================== consultas

    async def obtener(self, id_reserva: int, *, bloquear: bool = False) -> Reserva:
        consulta = select(Reserva).where(Reserva.id_reserva == id_reserva).options(*opciones_reserva())
        if bloquear:
            consulta = consulta.with_for_update(of=Reserva)
        reserva = await self.sesion.scalar(consulta.execution_options(populate_existing=True))
        if reserva is None:
            raise ErrorNoEncontrado(f"No existe la reserva #{id_reserva}.")
        return reserva

    async def listar(
        self,
        paginacion: ParametrosPaginacion,
        *,
        fecha: date | None = None,
        estado: EstadoReserva | None = None,
        id_dispositivo: int | None = None,
    ) -> Pagina[Reserva]:
        consulta = select(Reserva).options(*opciones_reserva())
        if fecha is not None:
            consulta = consulta.where(Reserva.fecha == fecha)
        if estado is not None:
            consulta = consulta.where(Reserva.estado == estado)
        if id_dispositivo is not None:
            consulta = consulta.where(Reserva.id_dispositivo == id_dispositivo)
        consulta = consulta.order_by(Reserva.fecha, Reserva.hora_inicio, Reserva.id_reserva)
        return await paginar(self.sesion, consulta, paginacion, lambda r: r)

    async def dispositivos_del_tipo(self, tipo: TipoDispositivo) -> Sequence[Dispositivo]:
        consulta = select(Dispositivo).where(Dispositivo.tipo == tipo).order_by(Dispositivo.numero_serie)
        return (await self.sesion.scalars(consulta)).all()
