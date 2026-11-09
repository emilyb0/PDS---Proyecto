"""Datos semilla para la demo (especificación, sección 13; RESTR01).

Uso (PowerShell, en la raíz del proyecto)::

    docker compose exec api python -m app.semilla              # idempotente: si ya hay datos, no hace nada
    docker compose exec api python -m app.semilla --reiniciar  # borra todo (también los videos) y vuelve a sembrar

Carga lo mínimo para la demostración, para que el resto se cree en vivo:

- 2 usuarios: la administradora Emily Bonilla y el operador Santiago Figueroa (el esquema exige que toda
  reserva tenga un operador activo como responsable). Contraseñas de desarrollo, documentadas en el README.
- 6 dispositivos: 4 robots y 2 drones, con baterías distintas. R-003 tiene la batería baja y R-004 el LIDAR en
  falla (para mostrar RF07).
- Un campus **de ejemplo** (coordenadas inventadas cerca de Bogotá).
- 5 reservas: 3 servicios ya terminados (con ruta, incidencias, alertas de RF11 y video de RF12) y 2 programadas
  para mañana.
- Sin registros de auditoría: la auditoría empieza vacía y se llena con lo que se haga en la demo.

Todo es determinista (semilla fija), salvo las fechas, que se calculan desde hoy.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.alertas.modelos import AlertaServicio
from app.config import Configuracion
from app.contenedor import Contenedor
from app.dispositivos.modelos import SENSORES_POR_TIPO, Dispositivo, Drone, Robot, Sensor
from app.dominio.geometria import distancia_m
from app.integraciones.almacenamiento import ErrorAlmacenamiento
from app.nucleo.enums import (
    CausaAlerta,
    EstadoReserva,
    EstadoSensor,
    EstadoServicio,
    RolUsuario,
    TipoDispositivo,
    TipoIncidencia,
    TipoServicio,
)
from app.nucleo.registro import configurar_registro
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio, RegistroTelemetria
from app.ubicaciones.modelos import Ubicacion
from app.usuarios.modelos import Usuario
from app.videos.gestor_videos import GestorVideos
from app.videos.modelos import Video

registro = logging.getLogger(__name__)

NOMBRE_ADMIN = "Emily Bonilla"
CORREO_ADMIN = "emily.bonilla@campus.edu.co"
CONTRASENA_ADMIN = "Admin123*"
NOMBRE_OPERADOR = "Santiago Figueroa"
CORREO_OPERADOR = "santiago.figueroa@campus.edu.co"
CONTRASENA_OPERADOR = "Operador123*"
VIDEO_MUESTRA = Path(__file__).resolve().parent / "integraciones" / "dispositivo" / "muestra.mp4"

# Campus DE EJEMPLO: coordenadas inventadas cerca de Bogotá.
UBICACIONES = {
    "Base de operaciones": (4.6380, -74.0840),
    "Cafetería": (4.6390, -74.0830),
    "Rectoría": (4.6400, -74.0820),
    "Biblioteca": (4.6372, -74.0826),
    "Bloque A": (4.6395, -74.0848),
    "Bloque B": (4.6408, -74.0836),
    "Coliseo": (4.6412, -74.0852),
    "Cancha principal": (4.6366, -74.0845),
}

# numero_serie, tipo, modelo, batería, horas de uso desde el último mantenimiento, sensores en falla
DISPOSITIVOS = [
    ("R-001", TipoDispositivo.ROBOT, "Rover Mk2", 95, "12.40", ()),
    ("R-002", TipoDispositivo.ROBOT, "Rover Mk2", 82, "20.10", ()),
    ("R-003", TipoDispositivo.ROBOT, "Rover Mini", 28, "8.30", ()),
    ("R-004", TipoDispositivo.ROBOT, "Rover Mk2", 74, "30.00", ("LIDAR",)),
    ("D-001", TipoDispositivo.DRONE, "Halcón X4", 90, "10.70", ()),
    ("D-002", TipoDispositivo.DRONE, "Halcón X4", 76, "35.20", ()),
]

# Servicios ya terminados: días atrás, hora, dispositivo, origen, destino, tipo, minutos estimados y la alerta
# de servicio (RF11) que tuvieron. R-004 no aparece: tiene el LIDAR en falla y RF07 no lo deja reservar.
HISTORIAL = [
    (6, time(10, 0), "R-001", "Cafetería", "Rectoría", TipoServicio.PEDIDO_CAFETERIA, 20, None),
    (3, time(11, 30), "D-001", "Base de operaciones", "Coliseo", TipoServicio.GRABACION_EVENTO, 30, "sensor"),
    (1, time(15, 0), "R-002", "Biblioteca", "Bloque A", TipoServicio.ENTREGA_DOCUMENTOS, 30, "bateria"),
]

# Reservas programadas para mañana: hora, dispositivo, origen, destino, tipo y minutos estimados.
PROGRAMADAS = [
    (time(9, 0), "R-001", "Rectoría", "Biblioteca", TipoServicio.ENTREGA_DOCUMENTOS, 30),
    (time(10, 0), "D-002", "Base de operaciones", "Cancha principal", TipoServicio.GRABACION_EVENTO, 45),
]


@dataclass
class ResumenSemilla:
    sembrada: bool
    conteos: dict[str, int] = field(default_factory=dict)


# ============================================================================ utilidades


def _punto_en(ruta: list[tuple[float, float]], fraccion: float) -> tuple[float, float]:
    """Punto de la poligonal al ``fraccion`` (0–1) de su largo."""
    tramos = [distancia_m(a, b) for a, b in pairwise(ruta)]
    objetivo = sum(tramos) * max(0.0, min(1.0, fraccion))
    for (a, b), largo in zip(pairwise(ruta), tramos, strict=True):
        if objetivo <= largo:
            f = 0 if largo == 0 else objetivo / largo
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        objetivo -= largo
    return ruta[-1]


async def _tablas(contenedor: Contenedor) -> list[str]:
    async with contenedor.sesiones() as sesion:
        filas = await sesion.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        )
        return [fila[0] for fila in filas]


async def vaciar(contenedor: Contenedor) -> None:
    """Borra todos los datos y los videos guardados (no toca el esquema)."""
    async with contenedor.sesiones() as sesion:
        urls = (await sesion.scalars(select(Video.url).where(Video.fecha_eliminacion.is_(None)))).all()
    for url in urls:
        try:
            await contenedor.almacenamiento.eliminar(url)
        except ErrorAlmacenamiento as error:
            registro.warning("No se pudo borrar %s: %s", url, error)
    async with contenedor.sesiones() as sesion:
        await sesion.execute(text(f"TRUNCATE {', '.join(await _tablas(contenedor))} RESTART IDENTITY CASCADE"))
        await sesion.commit()


# ============================================================================ siembra


async def sembrar(contenedor: Contenedor, *, reiniciar: bool = False) -> ResumenSemilla:
    if reiniciar:
        await vaciar(contenedor)
    async with contenedor.sesiones() as sesion:
        if await sesion.scalar(select(Usuario.id_usuario).where(Usuario.correo_institucional == CORREO_ADMIN)):
            return ResumenSemilla(sembrada=False)

    azar = random.Random(42)
    reloj = contenedor.reloj
    ahora = reloj.ahora().replace(microsecond=0)
    hoy = ahora.date()
    video = VIDEO_MUESTRA.read_bytes()

    async with contenedor.sesiones() as sesion:
        # ------------------------------------------------------------ usuarios
        admin = Usuario(
            nombre=NOMBRE_ADMIN,
            correo_institucional=CORREO_ADMIN,
            contrasena_hash=contenedor.cifrador.cifrar(CONTRASENA_ADMIN),
            rol=RolUsuario.ADMINISTRADOR,
            fecha_creacion=ahora - timedelta(days=30),
        )
        operador = Usuario(
            nombre=NOMBRE_OPERADOR,
            correo_institucional=CORREO_OPERADOR,
            contrasena_hash=contenedor.cifrador.cifrar(CONTRASENA_OPERADOR),
            rol=RolUsuario.OPERADOR,
            fecha_creacion=ahora - timedelta(days=30),
        )
        sesion.add_all([admin, operador])

        # ------------------------------------------------------------ campus de ejemplo
        lugares = {
            nombre: Ubicacion(nombre=nombre, latitud=Decimal(str(lat)), longitud=Decimal(str(lon)))
            for nombre, (lat, lon) in UBICACIONES.items()
        }
        sesion.add_all(lugares.values())

        # ------------------------------------------------------------ dispositivos
        dispositivos: dict[str, Dispositivo] = {}
        for serie, tipo, modelo, bateria, horas, falla in DISPOSITIVOS:
            clase = Robot if tipo == TipoDispositivo.ROBOT else Drone
            dispositivos[serie] = clase(
                numero_serie=serie,
                modelo=modelo,
                nivel_bateria=bateria,
                horas_uso_desde_mant=Decimal(horas),
                capacidad_carga_kg=Decimal("5.00" if modelo == "Rover Mk2" else "3.00")
                if tipo == TipoDispositivo.ROBOT
                else None,
                autonomia_vuelo_min=25 if tipo == TipoDispositivo.DRONE else None,
                fecha_registro=hoy - timedelta(days=30),
                sensores=[
                    Sensor(nombre=n, estado=EstadoSensor.FALLA if n in falla else EstadoSensor.OK)
                    for n in SENSORES_POR_TIPO[tipo]
                ],
            )
        sesion.add_all(dispositivos.values())
        await sesion.flush()

        def nueva_reserva(
            serie: str, origen: str, destino: str, tipo_servicio: TipoServicio, inicio: datetime, duracion: int
        ) -> Reserva:
            dispositivo = dispositivos[serie]
            return Reserva(
                id_administrador=admin.id_usuario,
                id_operador=operador.id_usuario,
                id_dispositivo=dispositivo.id_dispositivo,
                id_origen=lugares[origen].id_ubicacion,
                id_destino=lugares[destino].id_ubicacion,
                tipo_servicio=tipo_servicio,
                fecha=inicio.date(),
                hora_inicio=inicio.time(),
                duracion_estimada_min=duracion,
                estado=EstadoReserva.PROGRAMADA,
                # El trigger exige el código de entrega en los robots.
                codigo_entrega=f"{azar.randrange(10_000):04d}" if dispositivo.tipo == TipoDispositivo.ROBOT else None,
                fecha_creacion=min(ahora, inicio) - timedelta(days=1),
            )

        # ------------------------------------------------------------ servicios terminados (RF08, RF11, RF12)
        for dias, hora, serie, origen, destino, tipo_servicio, duracion, evento in HISTORIAL:
            inicio = datetime.combine(hoy - timedelta(days=dias), hora)
            reserva = nueva_reserva(serie, origen, destino, tipo_servicio, inicio, duracion)
            reserva.estado = EstadoReserva.FINALIZADA
            sesion.add(reserva)
            await sesion.flush()
            salida = inicio + timedelta(seconds=5)
            regreso = salida + timedelta(minutes=duracion * 0.8)
            bitacora = BitacoraServicio(
                id_reserva=reserva.id_reserva,
                hora_salida=salida,
                hora_regreso=regreso,
                estado=EstadoServicio.FINALIZADO,
            )
            sesion.add(bitacora)
            await sesion.flush()
            await _ruta_e_incidencias(sesion, azar, bitacora, dispositivos[serie], origen, destino, evento)
            duracion_seg = int((regreso - salida).total_seconds())
            url = await contenedor.almacenamiento.subir(video, GestorVideos.nombre_objeto(bitacora.id_bitacora, salida))
            GestorVideos.registrar_video(sesion, bitacora.id_bitacora, url, salida, duracion_seg)

        # ------------------------------------------------------------ reservas programadas para mañana
        manana = hoy + timedelta(days=1)
        for hora, serie, origen, destino, tipo_servicio, duracion in PROGRAMADAS:
            reserva = nueva_reserva(serie, origen, destino, tipo_servicio, datetime.combine(manana, hora), duracion)
            sesion.add(reserva)
            await sesion.flush()
        await sesion.commit()

    conteos = {}
    async with contenedor.sesiones() as sesion:
        for tabla in (
            "usuario",
            "dispositivo",
            "ubicacion",
            "reserva",
            "bitacora_servicio",
            "registro_telemetria",
            "incidencia",
            "alerta",
            "video",
        ):
            conteos[tabla] = int(await sesion.scalar(text(f"SELECT count(*) FROM {tabla}")) or 0)
    return ResumenSemilla(sembrada=True, conteos=conteos)


async def _ruta_e_incidencias(
    sesion: AsyncSession,
    azar: random.Random,
    bitacora: BitacoraServicio,
    dispositivo: Dispositivo,
    origen: str,
    destino: str,
    evento: str | None,
) -> None:
    """Ruta (un punto cada 30 s, con la lectura de cada sensor) e incidencias y alertas del servicio (RF11)."""
    es_drone = dispositivo.tipo == TipoDispositivo.DRONE
    base = UBICACIONES["Base de operaciones"]
    ida = (
        [base, UBICACIONES[origen], UBICACIONES[destino]]
        if origen != "Base de operaciones"
        else [base, UBICACIONES[destino]]
    )
    ruta = [*ida, base]
    salida, regreso = bitacora.hora_salida, bitacora.hora_regreso
    assert regreso is not None
    total = (regreso - salida).total_seconds()
    consumo = 2.0 if es_drone else 1.0
    bateria_inicial = azar.randint(70, 100)
    sensor_falla = "Cámara" if evento == "sensor" else None
    momento_falla = salida + timedelta(seconds=total * 0.4)
    puntos = []
    paso = 0.0
    while paso <= total:
        momento = salida + timedelta(seconds=paso)
        f = paso / total if total else 1.0
        if es_drone:  # vuela un cuarto, graba la mitad en el destino y vuelve
            avance = f * 2 if f < 0.25 else (0.5 if f < 0.75 else 0.5 + (f - 0.75) * 2)
            fase = "EN_RUTA" if f < 0.25 else ("EN_DESTINO" if f < 0.75 else "RETORNANDO")
        else:
            avance, fase = f, ("EN_RUTA" if f < 0.5 else "RETORNANDO")
        lat, lon = _punto_en(ruta, avance)
        bateria = max(0, round(bateria_inicial - consumo * paso / 60))
        if evento == "bateria" and f >= 0.5:
            bateria = min(bateria, 18)
        lecturas = {
            s.id_sensor: EstadoSensor.FALLA
            if (s.nombre == sensor_falla and momento >= momento_falla) or s.estado == EstadoSensor.FALLA
            else EstadoSensor.OK
            for s in dispositivo.sensores
        }
        puntos.append(bitacora.registrar_punto(momento, lat, lon, bateria, fase, lecturas))
        paso += 30
    sesion.add_all(puntos)

    def punto_a(fraccion: float) -> RegistroTelemetria:
        return puntos[min(len(puntos) - 1, int(len(puntos) * fraccion))]

    async def alerta(causa: CausaAlerta, descripcion: str, fraccion: float) -> None:
        punto = punto_a(fraccion)
        incidencia = bitacora.registrar_incidencia(
            TipoIncidencia(causa.value), descripcion, punto.fecha_hora, float(punto.latitud), float(punto.longitud)
        )
        sesion.add(incidencia)
        await sesion.flush()
        sesion.add(
            AlertaServicio(
                id_dispositivo=dispositivo.id_dispositivo,
                fecha_hora=punto.fecha_hora,
                descripcion=descripcion[:255],
                causa=causa,
                id_incidencia=incidencia.id_incidencia,
            )
        )
        await sesion.flush()

    serie = dispositivo.numero_serie
    if evento == "bateria":
        await alerta(CausaAlerta.BATERIA_BAJA, f"{serie}: batería 18 % (mínimo 20 %)", 0.5)
    elif evento == "sensor":
        await alerta(CausaAlerta.SENSOR_EN_FALLA, f"{serie}: sensor Cámara en falla", 0.41)


# ============================================================================ comando


async def _ejecutar(reiniciar: bool) -> int:
    contenedor = Contenedor.crear(Configuracion(), modulos=[])
    try:
        resumen = await sembrar(contenedor, reiniciar=reiniciar)
    finally:
        await contenedor.cerrar()
    if not resumen.sembrada:
        print("La base ya tiene los datos semilla; no se cambió nada. Use --reiniciar para empezar de cero.")
        return 0
    print("Datos semilla cargados:")
    for tabla, cantidad in resumen.conteos.items():
        print(f"  {tabla}: {cantidad}")
    print(f"Administradora: {CORREO_ADMIN} / {CONTRASENA_ADMIN}")
    print(f"Operador:       {CORREO_OPERADOR} / {CONTRASENA_OPERADOR}")
    if reiniciar:
        print("Reinicie la API para que el simulador vuelva a leer los dispositivos: docker compose restart api")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga los datos semilla de la demo (idempotente).")
    parser.add_argument(
        "--reiniciar", action="store_true", help="borra todos los datos y los videos y vuelve a sembrar"
    )
    argumentos = parser.parse_args()
    configurar_registro("WARNING")
    fabrica = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=fabrica) as corredor:
        sys.exit(corredor.run(_ejecutar(argumentos.reiniciar)))


if __name__ == "__main__":
    main()
