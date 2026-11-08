"""Datos de prueba creados directamente en la base (más rápido que pasar por la API)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path

from app.contenedor import Contenedor
from app.dispositivos.modelos import SENSORES_POR_TIPO, Dispositivo, Drone, Robot, Sensor
from app.integraciones.dispositivo.simulador import ApiDispositivoSimulada
from app.mantenimiento.modelos import Mantenimiento
from app.nucleo.enums import (
    EstadoDispositivo,
    EstadoReserva,
    EstadoSensor,
    EstadoServicio,
    EstadoUsuario,
    RolUsuario,
    TipoDispositivo,
    TipoIncidencia,
    TipoMantenimiento,
    TipoServicio,
)
from app.nucleo.reloj import RelojSimulado
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio
from app.ubicaciones.modelos import Ubicacion, VerticeZona, ZonaOperacion
from app.usuarios.modelos import Usuario
from app.videos.gestor_videos import GestorVideos
from app.videos.modelos import Video

_secuencia = count(1)
RUTA_VIDEO_MUESTRA = Path(__file__).resolve().parents[1] / "app" / "integraciones" / "dispositivo" / "muestra.mp4"


async def crear_usuario(
    contenedor: Contenedor,
    *,
    rol: RolUsuario = RolUsuario.OPERADOR,
    nombre: str | None = None,
    correo: str | None = None,
    contrasena: str = "Clave1234*",
    estado: EstadoUsuario = EstadoUsuario.ACTIVO,
) -> Usuario:
    numero = next(_secuencia)
    usuario = Usuario(
        nombre=nombre or f"Usuario {numero}",
        correo_institucional=(correo or f"usuario{numero}@campus.edu.co").lower(),
        contrasena_hash=contenedor.cifrador.cifrar(contrasena),
        rol=rol,
        estado=estado,
        fecha_creacion=contenedor.reloj.ahora(),
    )
    async with contenedor.sesiones() as sesion:
        sesion.add(usuario)
        await sesion.commit()
    return usuario


def encabezados(contenedor: Contenedor, usuario: Usuario) -> dict[str, str]:
    token = contenedor.tokens.emitir(usuario.id_usuario, usuario.rol.value).token
    return {"Authorization": f"Bearer {token}"}


async def crear_dispositivo(
    contenedor: Contenedor,
    *,
    tipo: TipoDispositivo = TipoDispositivo.ROBOT,
    numero_serie: str | None = None,
    estado: EstadoDispositivo = EstadoDispositivo.DISPONIBLE,
    nivel_bateria: int = 100,
    horas_uso: str = "0",
    fecha_registro: date | None = None,
    sensores_en_falla: tuple[str, ...] = (),
    fecha_baja: date | None = None,
) -> Dispositivo:
    numero = next(_secuencia)
    clase = Robot if tipo == TipoDispositivo.ROBOT else Drone
    dispositivo = clase(
        numero_serie=numero_serie or f"{'R' if tipo == TipoDispositivo.ROBOT else 'D'}-{numero:03d}",
        modelo="Rover Mk2" if tipo == TipoDispositivo.ROBOT else "Halcón X4",
        estado=estado,
        nivel_bateria=nivel_bateria,
        horas_uso_desde_mant=Decimal(horas_uso),
        capacidad_carga_kg=Decimal("5.00") if tipo == TipoDispositivo.ROBOT else None,
        autonomia_vuelo_min=25 if tipo == TipoDispositivo.DRONE else None,
        fecha_registro=fecha_registro or contenedor.reloj.hoy(),
        fecha_baja=fecha_baja,
        motivo_baja="Retirado" if fecha_baja else None,
        sensores=[
            Sensor(nombre=n, estado=EstadoSensor.FALLA if n in sensores_en_falla else EstadoSensor.OK)
            for n in SENSORES_POR_TIPO[tipo]
        ],
    )
    async with contenedor.sesiones() as sesion:
        sesion.add(dispositivo)
        await sesion.commit()
    return dispositivo


async def crear_ubicaciones(contenedor: Contenedor) -> dict[str, Ubicacion]:
    """Campus de ejemplo pequeño (coordenadas inventadas)."""
    puntos = {
        "Base de operaciones": ("4.638000", "-74.084000"),
        "Cafetería": ("4.639000", "-74.083000"),
        "Rectoría": ("4.640000", "-74.082000"),
        "Coliseo": ("4.641000", "-74.085000"),
    }
    ubicaciones = {
        nombre: Ubicacion(nombre=nombre, latitud=Decimal(lat), longitud=Decimal(lon))
        for nombre, (lat, lon) in puntos.items()
    }
    async with contenedor.sesiones() as sesion:
        sesion.add_all(ubicaciones.values())
        await sesion.commit()
    return ubicaciones


async def crear_zona(
    contenedor: Contenedor, nombre: str = "Campus de ejemplo", vertices: list[tuple[str, str]] | None = None
) -> ZonaOperacion:
    vertices = vertices or [("4.630", "-74.090"), ("4.650", "-74.090"), ("4.650", "-74.070"), ("4.630", "-74.070")]
    zona = ZonaOperacion(
        nombre=nombre,
        vertices=[
            VerticeZona(orden=i, latitud=Decimal(lat), longitud=Decimal(lon))
            for i, (lat, lon) in enumerate(vertices, 1)
        ],
    )
    async with contenedor.sesiones() as sesion:
        sesion.add(zona)
        await sesion.commit()
    return zona


async def crear_reserva(
    contenedor: Contenedor,
    *,
    administrador: Usuario,
    operador: Usuario,
    dispositivo: Dispositivo,
    origen: Ubicacion,
    destino: Ubicacion,
    fecha: date,
    hora_inicio: time,
    duracion_min: int = 30,
    estado: EstadoReserva = EstadoReserva.PROGRAMADA,
    tipo_servicio: TipoServicio | None = None,
) -> Reserva:
    es_robot = dispositivo.tipo == TipoDispositivo.ROBOT
    reserva = Reserva(
        id_administrador=administrador.id_usuario,
        id_operador=operador.id_usuario,
        id_dispositivo=dispositivo.id_dispositivo,
        id_origen=origen.id_ubicacion,
        id_destino=destino.id_ubicacion,
        tipo_servicio=tipo_servicio or (TipoServicio.ENTREGA_DOCUMENTOS if es_robot else TipoServicio.GRABACION_EVENTO),
        fecha=fecha,
        hora_inicio=hora_inicio,
        duracion_estimada_min=duracion_min,
        estado=estado,
        codigo_entrega="1234" if es_robot else None,
        motivo_cambio="Prueba" if estado == EstadoReserva.CANCELADA else None,
        fecha_creacion=contenedor.reloj.ahora(),
    )
    async with contenedor.sesiones() as sesion:
        sesion.add(reserva)
        await sesion.commit()
    return reserva


async def crear_mantenimiento(
    contenedor: Contenedor,
    *,
    dispositivo: Dispositivo,
    operador: Usuario,
    fecha_inicio: date,
    fecha_fin: date | None = None,
    tipo: TipoMantenimiento = TipoMantenimiento.PREVENTIVO,
) -> Mantenimiento:
    mantenimiento = Mantenimiento(
        id_dispositivo=dispositivo.id_dispositivo,
        id_operador=operador.id_usuario,
        tipo=tipo,
        descripcion="Mantenimiento de prueba",
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    async with contenedor.sesiones() as sesion:
        sesion.add(mantenimiento)
        await sesion.commit()
    return mantenimiento


def hace(dias: int, desde: datetime | date) -> date:
    """Fecha ``dias`` días antes de ``desde``."""
    base = desde.date() if isinstance(desde, datetime) else desde
    return date.fromordinal(base.toordinal() - dias)


def datos_reserva(
    lugares: dict[str, Ubicacion],
    dispositivo: Dispositivo,
    operador: Usuario,
    **cambios: object,
) -> dict[str, object]:
    """Cuerpo de ``POST /api/reservas``: hoy (9 de noviembre de 2026) de 10:00 a 10:30, de la Cafetería a la Rectoría
    (robots) o de la Base al Coliseo (drones)."""
    es_robot = dispositivo.tipo == TipoDispositivo.ROBOT
    datos: dict[str, object] = {
        "tipo_servicio": "PEDIDO_CAFETERIA" if es_robot else "GRABACION_EVENTO",
        "fecha": "2026-11-09",
        "hora_inicio": "10:00",
        "duracion_estimada_min": 30,
        "id_origen": lugares["Cafetería" if es_robot else "Base de operaciones"].id_ubicacion,
        "id_destino": lugares["Rectoría" if es_robot else "Coliseo"].id_ubicacion,
        "id_dispositivo": dispositivo.id_dispositivo,
        "id_operador": operador.id_usuario,
    }
    datos.update(cambios)
    return datos


def simulador_de(contenedor: Contenedor) -> ApiDispositivoSimulada:
    simulador = contenedor.api_dispositivo
    assert isinstance(simulador, ApiDispositivoSimulada)
    return simulador


async def servicio_en_curso(
    contenedor: Contenedor,
    *,
    administrador: Usuario,
    operador: Usuario,
    lugares: dict[str, Ubicacion],
    tipo: TipoDispositivo = TipoDispositivo.ROBOT,
    hora_inicio: time = time(10, 0),
    duracion_min: int = 30,
    dispositivo: Dispositivo | None = None,
) -> tuple[Dispositivo, Reserva, int]:
    """Crea una reserva para hoy, pone el reloj a su hora de inicio y la inicia con el monitor.

    Los robots van de la Cafetería a la Rectoría y los drones de la Base al Coliseo. Devuelve el dispositivo, la
    reserva y el id de la bitácora.
    """
    dispositivo = dispositivo or await crear_dispositivo(contenedor, tipo=tipo)
    es_robot = dispositivo.tipo == TipoDispositivo.ROBOT
    reserva = await crear_reserva(
        contenedor,
        administrador=administrador,
        operador=operador,
        dispositivo=dispositivo,
        origen=lugares["Cafetería" if es_robot else "Base de operaciones"],
        destino=lugares["Rectoría" if es_robot else "Coliseo"],
        fecha=contenedor.reloj.hoy(),
        hora_inicio=hora_inicio,
        duracion_min=duracion_min,
    )
    reloj = contenedor.reloj
    assert isinstance(reloj, RelojSimulado)
    reloj.fijar(reserva.inicio)
    resultado = await contenedor.monitor.iniciar_servicio(reserva.id_reserva)
    assert resultado.resultado == "iniciada", resultado
    assert resultado.id_bitacora is not None
    return dispositivo, reserva, resultado.id_bitacora


async def ciclo(contenedor: Contenedor, **avance: float) -> None:
    """Avanza el reloj simulado, corre un ciclo de monitoreo y procesa los eventos del dispositivo."""
    reloj = contenedor.reloj
    assert isinstance(reloj, RelojSimulado)
    if avance:
        reloj.avanzar(**avance)
    await contenedor.monitor.actualizar_monitoreo()
    await contenedor.monitor.procesar_eventos_pendientes()


async def crear_servicio_finalizado(
    contenedor: Contenedor,
    *,
    administrador: Usuario,
    operador: Usuario,
    dispositivo: Dispositivo,
    origen: Ubicacion,
    destino: Ubicacion,
    salida: datetime,
    minutos: int = 20,
    tipo_servicio: TipoServicio | None = None,
    incidencias: tuple[TipoIncidencia, ...] = (),
    con_video: bool = True,
    en_curso: bool = False,
) -> tuple[Reserva, BitacoraServicio, Video | None]:
    """Un servicio ya terminado (o en curso) directamente en la base. El video se sube al almacenamiento de prueba.

    Duró el 80 % de lo estimado, como en el simulador.
    """
    es_robot = dispositivo.tipo == TipoDispositivo.ROBOT
    regreso = salida + timedelta(minutes=minutos * 0.8)
    reserva = Reserva(
        id_administrador=administrador.id_usuario,
        id_operador=operador.id_usuario,
        id_dispositivo=dispositivo.id_dispositivo,
        id_origen=origen.id_ubicacion,
        id_destino=destino.id_ubicacion,
        tipo_servicio=tipo_servicio or (TipoServicio.PEDIDO_CAFETERIA if es_robot else TipoServicio.GRABACION_EVENTO),
        fecha=salida.date(),
        hora_inicio=salida.time(),
        duracion_estimada_min=minutos,
        estado=EstadoReserva.EN_CURSO if en_curso else EstadoReserva.FINALIZADA,
        codigo_entrega="1234" if es_robot else None,
        fecha_creacion=salida - timedelta(days=1),
    )
    video = None
    async with contenedor.sesiones() as sesion:
        sesion.add(reserva)
        await sesion.flush()
        bitacora = BitacoraServicio(
            id_reserva=reserva.id_reserva,
            hora_salida=salida,
            hora_regreso=None if en_curso else regreso,
            estado=EstadoServicio.EN_CURSO if en_curso else EstadoServicio.FINALIZADO,
        )
        sesion.add(bitacora)
        await sesion.flush()
        for i, tipo in enumerate(incidencias):
            sesion.add(
                bitacora.registrar_incidencia(tipo, f"Incidencia de prueba {tipo}", salida + timedelta(minutes=i + 1))
            )
        if con_video and not en_curso:
            nombre = GestorVideos.nombre_objeto(bitacora.id_bitacora, salida)
            url = await contenedor.almacenamiento.subir(RUTA_VIDEO_MUESTRA.read_bytes(), nombre)
            video = GestorVideos.registrar_video(
                sesion, bitacora.id_bitacora, url, salida, int((regreso - salida).total_seconds())
            )
        await sesion.commit()
    return reserva, bitacora, video
