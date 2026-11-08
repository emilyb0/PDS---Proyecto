"""Los modelos de SQLAlchemy están bien mapeados a las tablas que crea esquema_bd.sql."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.alertas.modelos import Alerta, AlertaMantenimiento, AlertaServicio
from app.auditoria.modelos import RegistroAuditoria
from app.dispositivos.modelos import Dispositivo, Drone, Robot, Sensor
from app.mantenimiento.modelos import Mantenimiento
from app.nucleo.enums import (
    AccionAuditoria,
    CausaAlerta,
    EstadoReserva,
    EstadoSensor,
    EstadoServicio,
    TipoIncidencia,
    TipoMantenimiento,
    TipoServicio,
)
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio, RegistroTelemetria
from app.ubicaciones.modelos import Ubicacion, VerticeZona, ZonaOperacion
from app.usuarios.modelos import Usuario
from app.videos.modelos import Video

HOY = date(2026, 11, 9)
AHORA = datetime(2026, 11, 9, 8, 0)


async def test_grafo_completo_se_guarda_y_se_lee(sesion: AsyncSession, admin: Usuario, operador: Usuario) -> None:
    robot = Robot(
        numero_serie="R-001",
        modelo="Rover",
        capacidad_carga_kg=Decimal("5.00"),
        fecha_registro=HOY,
        sensores=[Sensor(nombre="GPS"), Sensor(nombre="LIDAR", estado=EstadoSensor.FALLA)],
    )
    drone = Drone(
        numero_serie="D-001",
        modelo="Halcón",
        autonomia_vuelo_min=25,
        fecha_registro=HOY,
        sensores=[Sensor(nombre="GPS")],
    )
    base = Ubicacion(nombre="Base", latitud=Decimal("4.6380"), longitud=Decimal("-74.0840"))
    destino = Ubicacion(nombre="Rectoría", latitud=Decimal("4.6390"), longitud=Decimal("-74.0830"))
    zona = ZonaOperacion(
        nombre="Campus",
        vertices=[
            VerticeZona(orden=1, latitud=Decimal("4.63"), longitud=Decimal("-74.09")),
            VerticeZona(orden=2, latitud=Decimal("4.65"), longitud=Decimal("-74.09")),
            VerticeZona(orden=3, latitud=Decimal("4.65"), longitud=Decimal("-74.07")),
        ],
    )
    sesion.add_all([robot, drone, base, destino, zona])
    await sesion.flush()

    reserva = Reserva(
        id_administrador=admin.id_usuario,
        id_operador=operador.id_usuario,
        id_dispositivo=robot.id_dispositivo,
        id_origen=base.id_ubicacion,
        id_destino=destino.id_ubicacion,
        tipo_servicio=TipoServicio.PEDIDO_CAFETERIA,
        fecha=HOY,
        hora_inicio=time(10, 0),
        duracion_estimada_min=30,
        codigo_entrega="1234",
        fecha_creacion=AHORA,
    )
    sesion.add(reserva)
    await sesion.flush()
    bitacora = BitacoraServicio(id_reserva=reserva.id_reserva, hora_salida=datetime(2026, 11, 9, 10, 0))
    sesion.add(bitacora)
    await sesion.flush()

    punto = bitacora.registrar_punto(
        datetime(2026, 11, 9, 10, 0, 5),
        4.6381,
        -74.0839,
        90,
        "EN_RUTA",
        {s.id_sensor: s.estado for s in robot.sensores},
    )
    incidencia = bitacora.registrar_incidencia(
        TipoIncidencia.BATERIA_BAJA, "Batería 19 %", datetime(2026, 11, 9, 10, 1), 4.6381, -74.0839
    )
    sesion.add_all([punto, incidencia])
    await sesion.flush()

    alerta = AlertaServicio(
        id_dispositivo=robot.id_dispositivo,
        fecha_hora=AHORA,
        descripcion="Batería baja",
        id_incidencia=incidencia.id_incidencia,
        causa=CausaAlerta.BATERIA_BAJA,
    )
    alerta_mant = AlertaMantenimiento(
        id_dispositivo=drone.id_dispositivo,
        fecha_hora=AHORA,
        descripcion="Mantenimiento preventivo",
        dias_desde_ultimo=30,
        horas_desde_ultimo=Decimal("12.50"),
    )
    mantenimiento = Mantenimiento(
        id_dispositivo=drone.id_dispositivo,
        id_operador=operador.id_usuario,
        tipo=TipoMantenimiento.PREVENTIVO,
        descripcion="Hélices",
        fecha_inicio=HOY,
    )
    video = Video(
        id_bitacora=bitacora.id_bitacora,
        url="local://videos/x.mp4",
        fecha_grabacion=bitacora.hora_salida,
        duracion_seg=60,
    )
    auditoria = RegistroAuditoria(
        id_usuario=admin.id_usuario,
        fecha_hora=AHORA,
        accion=AccionAuditoria.CREAR,
        entidad="reserva",
        id_entidad=reserva.id_reserva,
    )
    sesion.add_all([alerta, alerta_mant, mantenimiento, video, auditoria])
    await sesion.flush()
    sesion.add(alerta.registrar_atencion(operador.id_usuario, "Batería revisada", "Sin novedad", AHORA))
    bitacora.cerrar(datetime(2026, 11, 9, 10, 25))
    reserva.estado = EstadoReserva.FINALIZADA
    await sesion.commit()
    sesion.expunge_all()

    # Herencia de tabla única: se leen como Robot y Drone.
    dispositivos = (await sesion.scalars(select(Dispositivo).order_by(Dispositivo.id_dispositivo))).all()
    assert [type(d) for d in dispositivos] == [Robot, Drone]
    assert dispositivos[0].sensores_en_falla() == ["LIDAR"]
    assert not dispositivos[0].esta_apto()
    assert dispositivos[1].esta_apto()

    # Herencia joined: las alertas se leen con su subclase y la atención.
    alertas = (await sesion.scalars(select(Alerta).order_by(Alerta.id_alerta))).all()
    assert isinstance(alertas[0], AlertaServicio) and alertas[0].atendida
    assert isinstance(alertas[1], AlertaMantenimiento) and alertas[1].dias_desde_ultimo == 30

    # Columna calculada: horario [10:00, 10:30) que PostgreSQL arma solo.
    leida = await sesion.get(Reserva, reserva.id_reserva)
    assert leida is not None
    assert leida.horario.lower == datetime(2026, 11, 9, 10, 0)
    assert leida.horario.upper == datetime(2026, 11, 9, 10, 30)
    assert leida.hora_fin() == time(10, 30)

    leida_bitacora = await sesion.get(BitacoraServicio, bitacora.id_bitacora)
    assert leida_bitacora is not None
    assert leida_bitacora.estado == EstadoServicio.FINALIZADO
    assert leida_bitacora.horas_uso() == 0.42

    punto_leido = await sesion.scalar(select(RegistroTelemetria).options(selectinload(RegistroTelemetria.lecturas)))
    assert punto_leido is not None and len(punto_leido.lecturas) == 2

    zona_leida = await sesion.scalar(select(ZonaOperacion))
    assert zona_leida is not None and len(zona_leida.limites) == 3


def test_reserva_se_cruza_y_genera_codigo() -> None:
    a = Reserva(fecha=HOY, hora_inicio=time(10, 0), duracion_estimada_min=30)
    contigua = Reserva(fecha=HOY, hora_inicio=time(10, 30), duracion_estimada_min=30)
    cruzada = Reserva(fecha=HOY, hora_inicio=time(10, 15), duracion_estimada_min=30)
    assert not a.se_cruza_con(contigua)
    assert a.se_cruza_con(cruzada)
    codigos = {Reserva.generar_codigo_entrega() for _ in range(50)}
    assert all(len(c) == 4 and c.isdigit() for c in codigos)
