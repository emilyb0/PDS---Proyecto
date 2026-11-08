"""``MonitorServicios`` del núcleo: inicio, monitoreo, alertas y cierre de cada servicio (RF08–RF12).

- ``iniciar_reservas_pendientes`` (cada 10 s) e ``iniciar_servicio``: pasos 29–31 del diagrama de secuencia.
- ``actualizar_monitoreo`` (cada ``INTERVALO_MONITOREO_SEG``): consulta en paralelo todos los dispositivos que no
  están dados de baja, guarda la ruta, evalúa umbrales (RF11) y publica ``telemetria`` por SSE (RF09, RF10).
- ``procesar_evento``: avisos del dispositivo. ``LLEGADA_BASE`` cierra el servicio con su video (RF08, RF12);
  los demás (``CODIGO_INGRESADO`` de RF24) van a ``Extensiones.manejadores_evento``.
- ``reanudar_servicios``: al arrancar, los servicios abiertos siguen desde su último punto (decisión P1).

Un ``asyncio.Lock`` por dispositivo ordena el ciclo de monitoreo, los eventos, el inicio y las órdenes (RF14).
Los métodos ``enviar_orden`` (RF14), ``recibir_codigo_entrega`` (RF24) y ``verificar_zona`` (RF25) del diagrama
irán en sus módulos (pendientes; decisión M-9) y se engancharán con los puntos de extensión.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.alertas.modelos import AlertaServicio
from app.alertas.servicio import alertas_a_salida
from app.dispositivos.modelos import Dispositivo
from app.integraciones.dispositivo.interfaz import (
    ErrorDispositivo,
    EventoDispositivo,
    Fase,
    OrdenInicio,
    Punto,
    Reanudacion,
    TelemetriaDispositivo,
    TipoEvento,
)
from app.nucleo.enums import (
    CausaAlerta,
    EstadoDispositivo,
    EstadoReserva,
    EstadoSensor,
    EstadoServicio,
    TipoIncidencia,
)
from app.nucleo.errores import (
    ErrorDispositivoNoApto,
    ErrorNoEncontrado,
    ErrorReglaNegocio,
    ErrorServicioNoDisponible,
    es_error_bd,
)
from app.reservas.modelos import Reserva
from app.servicios.contexto import CondicionAlerta, ContextoMonitor
from app.servicios.eventos import datos_servicio, datos_telemetria
from app.servicios.modelos import BitacoraServicio, Incidencia, RegistroTelemetria
from app.ubicaciones.modelos import Ubicacion
from app.videos.gestor_videos import GestorVideos

if TYPE_CHECKING:
    from app.contenedor import Contenedor

registro = logging.getLogger(__name__)

INTENTOS_VIDEO = 3
ESPERA_ENTRE_INTENTOS_SEG = 1.0


def punto_de(ubicacion: Ubicacion) -> Punto:
    return Punto(float(ubicacion.latitud), float(ubicacion.longitud), ubicacion.nombre)


@dataclass(frozen=True)
class ResultadoInicio:
    resultado: str  # iniciada | en_espera | no_iniciada | cancelada | omitida
    id_reserva: int
    id_bitacora: int | None = None
    motivo: str | None = None


class MonitorServicios:
    def __init__(self, contenedor: Contenedor) -> None:
        self.c = contenedor
        self._candados: dict[int, asyncio.Lock] = {}
        self._ultimas: dict[int, dict[str, Any]] = {}  # id_dispositivo → último evento telemetria
        self._condiciones: dict[int, set[CausaAlerta]] = {}  # id_bitacora → causas activas (sin duplicados)
        self._avisos_inicio: dict[int, str] = {}  # id_reserva → último motivo avisado por SSE
        self._semaforo = asyncio.Semaphore(contenedor.config.monitor_concurrencia)
        self.ultimo_ciclo: datetime | None = None

    # ================================================================== utilidades

    def candado(self, id_dispositivo: int) -> asyncio.Lock:
        """Exclusión por dispositivo: monitoreo, eventos, inicio y órdenes no se pisan sobre la misma bitácora."""
        if id_dispositivo not in self._candados:
            self._candados[id_dispositivo] = asyncio.Lock()
        return self._candados[id_dispositivo]

    def ultima_telemetria(self, id_dispositivo: int) -> dict[str, Any] | None:
        return self._ultimas.get(id_dispositivo)

    async def _id_dispositivo(self, numero_serie: str) -> int | None:
        async with self.c.sesiones() as sesion:
            return await sesion.scalar(
                select(Dispositivo.id_dispositivo).where(Dispositivo.numero_serie == numero_serie)
            )

    @staticmethod
    async def servicio_abierto(
        sesion: AsyncSession, id_dispositivo: int, *, bloquear: bool = False
    ) -> tuple[BitacoraServicio, Reserva] | None:
        """La bitácora sin cerrar del dispositivo y su reserva (como mucho hay una: un servicio a la vez)."""
        consulta = (
            select(BitacoraServicio, Reserva)
            .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
            .where(Reserva.id_dispositivo == id_dispositivo, BitacoraServicio.estado != EstadoServicio.FINALIZADO)
            .order_by(BitacoraServicio.hora_salida.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if bloquear:
            consulta = consulta.with_for_update(of=[BitacoraServicio, Reserva])
        fila = (await sesion.execute(consulta)).first()
        return None if fila is None else (fila[0], fila[1])

    def _orden_inicio(self, reserva: Reserva, origen: Ubicacion, destino: Ubicacion, **extra: Any) -> OrdenInicio:
        orden = OrdenInicio(
            id_reserva=reserva.id_reserva,
            tipo_servicio=reserva.tipo_servicio,
            origen=punto_de(origen),
            destino=punto_de(destino),
            inicio=reserva.inicio,
            duracion_estimada_min=reserva.duracion_estimada_min,
            **extra,
        )
        # RF24 (si está activo) pide que el robot espere el código en el destino.
        for ajuste in self.c.extensiones.ajustes_orden_inicio:
            orden = ajuste(orden, reserva)
        return orden

    # ================================================================== inicio (pasos 29–31)

    async def iniciar_reservas_pendientes(self) -> dict[str, int]:
        """Tarea cada 10 s: intenta iniciar las reservas PROGRAMADA cuyo inicio ya llegó."""
        ahora = self.c.reloj.ahora()
        async with self.c.sesiones() as sesion:
            filas = (
                await sesion.execute(
                    select(Reserva.id_reserva, Reserva.id_dispositivo)
                    .where(Reserva.estado == EstadoReserva.PROGRAMADA, func.lower(Reserva.horario) <= ahora)
                    .order_by(func.lower(Reserva.horario), Reserva.id_reserva)
                )
            ).all()
        resumen: Counter[str] = Counter()
        for id_reserva, id_dispositivo in filas:
            try:
                async with self.candado(id_dispositivo):
                    resultado = await self._iniciar(id_reserva, forzado=False)
                resumen[resultado.resultado] += 1
            except Exception:
                registro.exception("No se pudo procesar el inicio de la reserva #%d", id_reserva)
                resumen["error"] += 1
        return dict(resumen)

    async def iniciar_servicio(self, id_reserva: int, *, forzado: bool = False) -> ResultadoInicio:
        """Inicia una reserva. Con ``forzado`` (control de demo) no espera la hora y explica con un error por qué
        no se puede (decisión D15)."""
        async with self.c.sesiones() as sesion:
            id_dispositivo = await sesion.scalar(select(Reserva.id_dispositivo).where(Reserva.id_reserva == id_reserva))
        if id_dispositivo is None:
            raise ErrorNoEncontrado(f"No existe la reserva #{id_reserva}.")
        async with self.candado(id_dispositivo):
            return await self._iniciar(id_reserva, forzado=forzado)

    def _avisar(self, reserva: Reserva, tipo: str, motivo: str, ahora: datetime, *, cancelada: bool = False) -> None:
        """Avisa una sola vez por SSE cada motivo por el que la reserva no inicia (sin repetirlo cada 10 s)."""
        if not cancelada and self._avisos_inicio.get(reserva.id_reserva) == motivo:
            return
        self._avisos_inicio[reserva.id_reserva] = motivo
        datos: dict[str, Any] = {
            "id_reserva": reserva.id_reserva,
            "id_dispositivo": reserva.id_dispositivo,
            "motivo": motivo,
            "fecha_hora": ahora,
        }
        if tipo == "servicio_no_iniciado":
            datos["cancelada"] = cancelada
        self.c.bus.publicar(tipo, datos)

    async def _iniciar(self, id_reserva: int, *, forzado: bool) -> ResultadoInicio:
        ahora = self.c.reloj.ahora()
        async with self.c.sesiones() as sesion:
            # Orden de bloqueo: primero la reserva y luego el dispositivo, igual que reprogramar (RF21).
            reserva = await sesion.scalar(
                select(Reserva)
                .where(Reserva.id_reserva == id_reserva)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if reserva is None:
                raise ErrorNoEncontrado(f"No existe la reserva #{id_reserva}.")
            if reserva.estado != EstadoReserva.PROGRAMADA:
                if forzado:
                    raise ErrorReglaNegocio(
                        f"La reserva #{id_reserva} no está programada (está {reserva.estado.value})."
                    )
                return ResultadoInicio("omitida", id_reserva)
            if not forzado and reserva.inicio > ahora:
                return ResultadoInicio("omitida", id_reserva)
            dispositivo = await sesion.scalar(
                select(Dispositivo)
                .where(Dispositivo.id_dispositivo == reserva.id_dispositivo)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            assert dispositivo is not None
            serie = dispositivo.numero_serie

            # La ventana terminó sin poder iniciar: se cancela con el último motivo conocido.
            if not forzado and reserva.fin <= ahora:
                motivo = self._avisos_inicio.pop(id_reserva, None) or "el dispositivo no estuvo disponible a tiempo"
                reserva.cancelar(f"No se inició: {motivo}"[:255])
                await sesion.commit()
                self._avisar(reserva, "servicio_no_iniciado", motivo, ahora, cancelada=True)
                self._avisos_inicio.pop(id_reserva, None)
                return ResultadoInicio("cancelada", id_reserva, motivo=motivo)

            # El dispositivo sigue en otro servicio: la reserva espera.
            otra = await sesion.scalar(
                select(Reserva.id_reserva).where(
                    Reserva.id_dispositivo == dispositivo.id_dispositivo,
                    Reserva.estado == EstadoReserva.EN_CURSO,
                    Reserva.id_reserva != id_reserva,
                )
            )
            if otra is not None:
                motivo = f"El dispositivo {serie} sigue en el servicio de la reserva #{otra}"
                self._avisar(reserva, "servicio_en_espera", motivo, ahora)
                if forzado:
                    raise ErrorReglaNegocio(motivo + ".")
                return ResultadoInicio("en_espera", id_reserva, motivo=motivo)

            # ¿Está apto? Estado y, en ese momento, batería y sensores (RF07).
            motivos = dispositivo.motivos_estado()
            if not motivos:
                try:
                    telemetria = await self.c.api_dispositivo.obtener_telemetria(serie)
                except ErrorDispositivo as error:
                    motivos = [f"El dispositivo {serie} no responde ({error})"]
                else:
                    dispositivo.actualizar_lectura(telemetria.nivel_bateria, telemetria.sensores)
                    motivos = dispositivo.motivos_no_apto(self.c.config.bateria_minima_asignacion)
            if motivos:
                await sesion.commit()  # guarda la lectura
                motivo = "; ".join(motivos)
                self._avisar(reserva, "servicio_no_iniciado", motivo, ahora)
                if forzado:
                    raise ErrorDispositivoNoApto(
                        f"No se puede iniciar la reserva #{id_reserva}: {motivo}.", {"motivos": motivos}
                    )
                return ResultadoInicio("no_iniciada", id_reserva, motivo=motivo)

            # Todo bien: orden de inicio, bitácora (RF08), reserva EN_CURSO y dispositivo EN_SERVICIO.
            origen = await sesion.get(Ubicacion, reserva.id_origen)
            destino = await sesion.get(Ubicacion, reserva.id_destino)
            assert origen is not None and destino is not None
            orden = self._orden_inicio(reserva, origen, destino)
            bitacora = BitacoraServicio(id_reserva=id_reserva, hora_salida=ahora, estado=EstadoServicio.EN_CURSO)
            sesion.add(bitacora)
            reserva.estado = EstadoReserva.EN_CURSO
            dispositivo.estado = EstadoDispositivo.EN_SERVICIO
            await sesion.flush()
            try:
                await self.c.api_dispositivo.enviar_orden_inicio(serie, orden)
            except ErrorDispositivo as error:
                await sesion.rollback()
                motivo = f"El dispositivo {serie} no recibió la orden de inicio ({error})"
                self._avisar(reserva, "servicio_no_iniciado", motivo, ahora)
                if forzado:
                    raise ErrorServicioNoDisponible(motivo + ".") from error
                return ResultadoInicio("no_iniciada", id_reserva, motivo=motivo)
            await sesion.commit()

        self._avisos_inicio.pop(id_reserva, None)
        self._condiciones[bitacora.id_bitacora] = set()
        registro.info("Servicio iniciado: reserva #%d, bitácora #%d, %s", id_reserva, bitacora.id_bitacora, serie)
        self.c.bus.publicar(
            "servicio",
            datos_servicio(bitacora.id_bitacora, id_reserva, reserva.id_dispositivo, "INICIADO", ahora),
        )
        return ResultadoInicio("iniciada", id_reserva, id_bitacora=bitacora.id_bitacora)

    # ================================================================== monitoreo (pasos 33–43)

    async def actualizar_monitoreo(self) -> int:
        """Un ciclo: consulta en paralelo todos los dispositivos que no están dados de baja. Devuelve cuántos
        respondieron. Si uno falla, se registra en el log y se sigue con los demás."""
        async with self.c.sesiones() as sesion:
            filas = (
                await sesion.execute(
                    select(Dispositivo.id_dispositivo, Dispositivo.numero_serie)
                    .where(Dispositivo.fecha_baja.is_(None))
                    .order_by(Dispositivo.id_dispositivo)
                )
            ).all()
        limite = self.c.config.intervalo_monitoreo_seg * 0.9
        resultados = await asyncio.gather(*(self._monitorear_a_tiempo(i, serie, limite) for i, serie in filas))
        self.ultimo_ciclo = self.c.reloj.ahora()
        return sum(resultados)

    async def _monitorear_a_tiempo(self, id_dispositivo: int, serie: str, limite: float) -> bool:
        try:
            await asyncio.wait_for(self.monitorear_dispositivo(id_dispositivo, serie), timeout=limite)
            return True
        except TimeoutError:
            registro.warning("Monitoreo: %s no respondió en %.1f s", serie, limite)
        except ErrorDispositivo as error:
            registro.warning("Monitoreo: %s", error)
        except Exception:
            registro.exception("Monitoreo: error con %s", serie)
        return False

    async def monitorear_dispositivo(self, id_dispositivo: int, serie: str) -> None:
        async with self.candado(id_dispositivo):
            telemetria = await self.c.api_dispositivo.obtener_telemetria(serie)
            async with self._semaforo, self.c.sesiones() as sesion:
                dispositivo = await sesion.scalar(
                    select(Dispositivo)
                    .where(Dispositivo.id_dispositivo == id_dispositivo)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if dispositivo is None or dispositivo.dado_de_baja:
                    return
                dispositivo.actualizar_lectura(telemetria.nivel_bateria, telemetria.sensores)
                if dispositivo.estado == EstadoDispositivo.EN_CARGA and telemetria.nivel_bateria >= 100:
                    dispositivo.estado = EstadoDispositivo.DISPONIBLE  # decisión D5

                abierto = await self.servicio_abierto(sesion, id_dispositivo)
                bitacora, reserva = abierto if abierto else (None, None)
                contexto = ContextoMonitor(sesion, self.c, dispositivo, telemetria, bitacora, reserva)
                if bitacora is not None:
                    await self._guardar_punto(sesion, bitacora, dispositivo, telemetria)
                    if telemetria.estado_servicio == Fase.RETORNANDO and bitacora.estado in (
                        EstadoServicio.EN_CURSO,
                        EstadoServicio.ENTREGADO,
                    ):
                        bitacora.estado = EstadoServicio.RETORNANDO
                    contexto.condiciones.extend(self.evaluar_umbrales(contexto))
                for verificacion in self.c.extensiones.verificaciones_monitor:
                    await verificacion(contexto)

                alertas: list[AlertaServicio] = []
                activas: set[CausaAlerta] = set()
                if bitacora is not None:
                    alertas, activas = await self._registrar_alertas(contexto)
                datos_alertas = await alertas_a_salida(sesion, alertas) if alertas else []
                await sesion.commit()

        if bitacora is not None:
            self._condiciones[bitacora.id_bitacora] = activas
        evento = datos_telemetria(
            dispositivo, telemetria, bitacora.id_bitacora if bitacora else None, contexto.datos_telemetria
        )
        self._ultimas[id_dispositivo] = evento
        self.c.bus.publicar("telemetria", evento)
        for datos in datos_alertas:
            self.c.bus.publicar("alerta", datos)
        for tipo, datos_evento in contexto.eventos:
            self.c.bus.publicar(tipo, datos_evento)
        for accion in contexto.despues:
            await accion()

    @staticmethod
    async def _guardar_punto(
        sesion: AsyncSession, bitacora: BitacoraServicio, dispositivo: Dispositivo, telemetria: TelemetriaDispositivo
    ) -> None:
        """Guarda un punto de la ruta con el estado de cada sensor. Un punto repetido se omite (decisión D18)."""
        lecturas = {
            sensor.id_sensor: EstadoSensor(telemetria.sensores[sensor.nombre])
            for sensor in dispositivo.sensores
            if sensor.nombre in telemetria.sensores
        }
        punto = bitacora.registrar_punto(
            telemetria.fecha_hora,
            telemetria.latitud,
            telemetria.longitud,
            telemetria.nivel_bateria,
            telemetria.estado_servicio.value,
            lecturas,
        )
        try:
            async with sesion.begin_nested():
                sesion.add(punto)
        except IntegrityError as error:
            if not es_error_bd(error, "23505", "uq_telemetria_punto"):
                raise
            registro.debug("Punto repetido de la bitácora #%d a las %s", bitacora.id_bitacora, telemetria.fecha_hora)

    def evaluar_umbrales(self, contexto: ContextoMonitor) -> list[CondicionAlerta]:
        """RF11: batería < BATERIA_ALERTA, algún sensor en falla, o retraso > RETRASO_ALERTA_MIN sobre el fin."""
        t, cfg = contexto.telemetria, self.c.config
        serie = contexto.dispositivo.numero_serie
        condiciones = []
        if t.nivel_bateria < cfg.bateria_alerta:
            condiciones.append(
                CondicionAlerta(
                    CausaAlerta.BATERIA_BAJA,
                    f"{serie}: batería {t.nivel_bateria} % (mínimo {cfg.bateria_alerta} %)",
                    t.latitud,
                    t.longitud,
                )
            )
        fallas = sorted(nombre for nombre, estado in t.sensores.items() if estado == EstadoSensor.FALLA)
        if fallas:
            texto = f"sensor {fallas[0]} en falla" if len(fallas) == 1 else f"sensores {', '.join(fallas)} en falla"
            condiciones.append(CondicionAlerta(CausaAlerta.SENSOR_EN_FALLA, f"{serie}: {texto}", t.latitud, t.longitud))
        reserva, bitacora = contexto.reserva, contexto.bitacora
        if reserva is not None and bitacora is not None and not bitacora.cerrada:
            ahora = self.c.reloj.ahora()
            if ahora > reserva.fin + timedelta(minutes=cfg.retraso_alerta_min):
                minutos = int((ahora - reserva.fin).total_seconds() // 60)
                condiciones.append(
                    CondicionAlerta(
                        CausaAlerta.RETRASO,
                        f"{serie}: {minutos} min de retraso sobre el fin estimado ({reserva.fin:%H:%M})",
                        t.latitud,
                        t.longitud,
                    )
                )
        return condiciones

    async def _registrar_alertas(self, contexto: ContextoMonitor) -> tuple[list[AlertaServicio], set[CausaAlerta]]:
        """Guarda las alertas nuevas sin duplicados: una causa vuelve a alertar solo si se normalizó y volvió a
        ocurrir. RETRASO sale una sola vez por servicio. Devuelve las alertas y las causas que quedan activas."""
        bitacora = contexto.bitacora
        assert bitacora is not None
        activas = self._condiciones.get(bitacora.id_bitacora)
        if activas is None:
            # Después de reiniciar: las causas que ya alertaron en este servicio cuentan como el mismo episodio.
            activas = set(
                (
                    await contexto.sesion.scalars(
                        select(AlertaServicio.causa)
                        .join(Incidencia, Incidencia.id_incidencia == AlertaServicio.id_incidencia)
                        .where(Incidencia.id_bitacora == bitacora.id_bitacora)
                    )
                ).all()
            )
        presentes: dict[CausaAlerta, CondicionAlerta] = {}
        for condicion in contexto.condiciones:
            presentes.setdefault(condicion.causa, condicion)

        ahora = self.c.reloj.ahora()
        alertas = []
        for causa, condicion in presentes.items():
            if causa in activas:
                continue
            incidencia = bitacora.registrar_incidencia(
                TipoIncidencia(causa.value), condicion.descripcion, ahora, condicion.latitud, condicion.longitud
            )
            contexto.sesion.add(incidencia)
            await contexto.sesion.flush()
            alerta = AlertaServicio(
                id_dispositivo=contexto.dispositivo.id_dispositivo,
                fecha_hora=ahora,
                descripcion=condicion.descripcion[:255],
                causa=causa,
                id_incidencia=incidencia.id_incidencia,
                dispositivo=contexto.dispositivo,
                atencion=None,
            )
            contexto.sesion.add(alerta)
            alertas.append(alerta)
            registro.info("Alerta %s: %s", causa.value, condicion.descripcion)
        if alertas:
            await contexto.sesion.flush()
        return alertas, set(presentes) | (activas & {CausaAlerta.RETRASO})

    # ================================================================== eventos del dispositivo

    async def procesar_evento(self, evento: EventoDispositivo) -> None:
        id_dispositivo = await self._id_dispositivo(evento.numero_serie)
        if id_dispositivo is None:
            registro.warning("Evento %s de un dispositivo desconocido: %s", evento.tipo, evento.numero_serie)
            return
        async with self.candado(id_dispositivo):
            if evento.tipo == TipoEvento.LLEGADA_BASE:
                await self.finalizar_servicio(id_dispositivo, evento.numero_serie, evento.fecha_hora)
                return
            manejador = self.c.extensiones.manejadores_evento.get(evento.tipo)
            if manejador is None:
                registro.info("Evento %s de %s sin manejador; se ignora.", evento.tipo, evento.numero_serie)
                return
            await manejador(self.c, evento, id_dispositivo)

    async def _procesar_seguro(self, evento: EventoDispositivo) -> None:
        try:
            await self.procesar_evento(evento)
        except Exception:
            registro.exception("No se pudo procesar el evento %s de %s", evento.tipo, evento.numero_serie)

    async def procesar_eventos_pendientes(self, espera: float = 0.05) -> int:
        """Procesa los eventos que ya están en cola (pruebas y controles de demo). Devuelve cuántos procesó."""
        procesados = 0
        while True:
            try:
                evento = await asyncio.wait_for(self.c.api_dispositivo.esperar_evento(), timeout=espera)
            except TimeoutError:
                return procesados
            await self._procesar_seguro(evento)
            procesados += 1

    async def consumir_eventos(self) -> None:
        """Tarea permanente: atiende los avisos del dispositivo a medida que llegan."""
        while True:
            evento = await self.c.api_dispositivo.esperar_evento()
            await self._procesar_seguro(evento)

    # ================================================================== cierre (pasos 55–63)

    async def finalizar_servicio(self, id_dispositivo: int, serie: str, hora_llegada: datetime) -> int | None:
        """El dispositivo llegó a la base: video, bitácora FINALIZADO, reserva FINALIZADA, estado y horas de uso.

        Se llama con el candado del dispositivo tomado. Devuelve el id de la bitácora cerrada.
        """
        ahora = self.c.reloj.ahora()
        async with self.c.sesiones() as sesion:
            abierto = await self.servicio_abierto(sesion, id_dispositivo)
        if abierto is None:
            registro.warning("%s llegó a la base sin un servicio abierto.", serie)
            return None
        bitacora, reserva = abierto
        id_bitacora = bitacora.id_bitacora
        hora_regreso = min(max(hora_llegada, bitacora.hora_salida), ahora)
        duracion_seg = max(1, int((hora_regreso - bitacora.hora_salida).total_seconds()))

        # 1. Video: se descarga y se sube FUERA de la transacción (si la subida falla, queda pendiente).
        url = None
        archivo = await self._descargar_video(serie, id_bitacora)
        if archivo is not None:
            url = await self.c.gestor_videos.almacenar_video(id_bitacora, bitacora.hora_salida, duracion_seg, archivo)
        try:
            telemetria: TelemetriaDispositivo | None = await self.c.api_dispositivo.obtener_telemetria(serie)
        except ErrorDispositivo:
            telemetria = None

        # 2. Todo el cierre en una transacción.
        async with self.c.sesiones() as sesion:
            abierto = await self.servicio_abierto(sesion, id_dispositivo, bloquear=True)
            if abierto is None or abierto[0].id_bitacora != id_bitacora:
                return None
            bitacora, reserva = abierto
            dispositivo = await sesion.scalar(
                select(Dispositivo)
                .where(Dispositivo.id_dispositivo == id_dispositivo)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            assert dispositivo is not None
            if telemetria is not None:
                dispositivo.actualizar_lectura(telemetria.nivel_bateria, telemetria.sensores)
                await self._guardar_punto(sesion, bitacora, dispositivo, telemetria)
            if url is not None:
                GestorVideos.registrar_video(sesion, id_bitacora, url, bitacora.hora_salida, duracion_seg)
            bitacora.cerrar(hora_regreso)
            reserva.estado = EstadoReserva.FINALIZADA
            if dispositivo.estado == EstadoDispositivo.EN_SERVICIO:
                bajo = dispositivo.nivel_bateria < self.c.config.bateria_minima_asignacion
                dispositivo.estado = EstadoDispositivo.EN_CARGA if bajo else EstadoDispositivo.DISPONIBLE
            dispositivo.horas_uso_desde_mant = Decimal(dispositivo.horas_uso_desde_mant or 0) + Decimal(
                str(bitacora.horas_uso() or 0)
            )
            # 3. Acciones de los módulos al cerrar (RF16: revisión preventiva).
            alertas: list[Any] = []
            for accion in self.c.extensiones.al_finalizar_servicio:
                alertas.extend(await accion(sesion, self.c, id_dispositivo) or [])
            datos_alertas = await alertas_a_salida(sesion, alertas) if alertas else []
            await sesion.commit()

        self._condiciones.pop(id_bitacora, None)
        registro.info("Servicio finalizado: bitácora #%d, %s (video: %s)", id_bitacora, serie, url or "pendiente")
        for datos in datos_alertas:
            self.c.bus.publicar("alerta", datos)
        self.c.bus.publicar(
            "servicio", datos_servicio(id_bitacora, reserva.id_reserva, id_dispositivo, "FINALIZADO", hora_regreso)
        )
        return id_bitacora

    async def _descargar_video(self, serie: str, id_bitacora: int) -> bytes | None:
        """Pide el video al dispositivo hasta ``INTENTOS_VIDEO`` veces. Si no lo entrega, el servicio se cierra sin
        video y queda el error en el log (decisión F5-11): sin el archivo no hay nada que reintentar después."""
        for intento in range(1, INTENTOS_VIDEO + 1):
            try:
                return await self.c.api_dispositivo.descargar_video(serie)
            except ErrorDispositivo as error:
                if intento == INTENTOS_VIDEO:
                    registro.error(
                        "%s no entregó el video de la bitácora #%d tras %d intentos (%s); se cierra sin video.",
                        serie,
                        id_bitacora,
                        INTENTOS_VIDEO,
                        error,
                    )
                    return None
                registro.warning("No se pudo descargar el video de %s (intento %d): %s", serie, intento, error)
                await asyncio.sleep(ESPERA_ENTRE_INTENTOS_SEG)
        return None

    # ================================================================== reinicio (decisión P1)

    async def reanudar_servicios(self) -> int:
        """Al arrancar: cada servicio abierto sigue en el simulador desde su último punto (o desde la base)."""
        pendientes = []
        async with self.c.sesiones() as sesion:
            filas = (
                await sesion.execute(
                    select(BitacoraServicio, Reserva, Dispositivo.numero_serie)
                    .join(Reserva, Reserva.id_reserva == BitacoraServicio.id_reserva)
                    .join(Dispositivo, Dispositivo.id_dispositivo == Reserva.id_dispositivo)
                    .where(BitacoraServicio.estado != EstadoServicio.FINALIZADO)
                    .options(joinedload(Reserva.origen), joinedload(Reserva.destino))
                )
            ).all()
            for bitacora, reserva, serie in filas:
                ultimo = await sesion.scalar(
                    select(RegistroTelemetria)
                    .where(RegistroTelemetria.id_bitacora == bitacora.id_bitacora)
                    .order_by(RegistroTelemetria.fecha_hora.desc())
                    .limit(1)
                )
                fase = None
                if ultimo is not None and ultimo.estado_servicio in Fase.__members__:
                    fase = Fase(ultimo.estado_servicio)
                datos = Reanudacion(
                    hora_salida=bitacora.hora_salida,
                    ultimo_punto=Punto(float(ultimo.latitud), float(ultimo.longitud)) if ultimo else None,
                    hora_ultimo_punto=ultimo.fecha_hora if ultimo else None,
                    fase_reportada=fase,
                    regresando=bitacora.estado in (EstadoServicio.ENTREGADO, EstadoServicio.RETORNANDO),
                )
                pendientes.append(
                    (serie, self._orden_inicio(reserva, reserva.origen, reserva.destino, reanudacion=datos))
                )
        reanudados = 0
        for serie, orden in pendientes:
            try:
                await self.c.api_dispositivo.enviar_orden_inicio(serie, orden)
                reanudados += 1
            except ErrorDispositivo as error:
                registro.error("No se pudo reanudar el servicio de %s: %s", serie, error)
        if reanudados:
            registro.info("Se reanudaron %d servicio(s) abiertos.", reanudados)
        return reanudados
