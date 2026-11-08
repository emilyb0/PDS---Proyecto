"""Reglas puras del dominio, sin base de datos (especificación, sección 14): tipo requerido, umbrales de RF07 y RF16,
cruce de horarios, vencimiento de videos y cálculo de alertas del monitor (RF11)."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.dispositivos.modelos import Robot, Sensor
from app.dominio.reglas import tipo_requerido
from app.integraciones.dispositivo.interfaz import Fase, TelemetriaDispositivo
from app.nucleo.enums import CausaAlerta, EstadoSensor, EstadoServicio, TipoDispositivo, TipoServicio
from app.nucleo.reloj import RelojSimulado
from app.reservas.modelos import Reserva
from app.servicios.contexto import ContextoMonitor
from app.servicios.modelos import BitacoraServicio
from app.servicios.monitor import MonitorServicios
from app.videos.modelos import Video

HOY = date(2026, 11, 9)


def robot(bateria: int = 100, fallas: tuple[str, ...] = (), horas: str = "0") -> Robot:
    return Robot(
        numero_serie="R-001",
        nivel_bateria=bateria,
        horas_uso_desde_mant=Decimal(horas),
        sensores=[
            Sensor(nombre=n, estado=EstadoSensor.FALLA if n in fallas else EstadoSensor.OK) for n in ("GPS", "LIDAR")
        ],
    )


def test_tipo_requerido_por_servicio() -> None:
    assert tipo_requerido(TipoServicio.ENTREGA_DOCUMENTOS) == TipoDispositivo.ROBOT
    assert tipo_requerido(TipoServicio.PEDIDO_CAFETERIA) == TipoDispositivo.ROBOT
    assert tipo_requerido(TipoServicio.GRABACION_EVENTO) == TipoDispositivo.DRONE


@pytest.mark.parametrize(("bateria", "apto"), [(29, False), (30, True)])
def test_rf07_umbral_de_bateria_para_asignar(bateria: int, apto: bool) -> None:
    assert robot(bateria).esta_apto(30) is apto


def test_rf07_motivos_de_no_apto() -> None:
    assert robot(25, ("LIDAR",)).motivos_no_apto(30) == ["Batería 25 % (mínimo 30 %)", "Sensor LIDAR en falla"]
    assert robot(90).motivos_no_apto(30) == []


@pytest.mark.parametrize(
    ("dias", "horas", "requiere"),
    [(29, "49.99", False), (30, "0", True), (0, "50.00", True), (29, "0", False)],
)
def test_rf16_30_dias_o_50_horas(dias: int, horas: str, requiere: bool) -> None:
    ultimo = date.fromordinal(HOY.toordinal() - dias)
    assert robot(horas=horas).requiere_mantenimiento(ultimo, HOY, 30, 50) is requiere


def test_rf06_cruce_de_horarios_y_contiguas() -> None:
    def reserva(inicio: time, minutos: int) -> Reserva:
        return Reserva(fecha=HOY, hora_inicio=inicio, duracion_estimada_min=minutos)

    assert reserva(time(10, 0), 30).se_cruza_con(reserva(time(10, 15), 30))
    assert not reserva(time(10, 0), 30).se_cruza_con(reserva(time(10, 30), 30))  # contiguas
    assert not reserva(time(10, 30), 30).se_cruza_con(reserva(time(10, 0), 30))


def test_rf26_vencimiento_en_meses_de_calendario() -> None:
    assert Video(fecha_grabacion=datetime(2026, 8, 9, 23, 0)).esta_vencido(HOY, 3)
    assert not Video(fecha_grabacion=datetime(2026, 8, 10, 0, 0)).esta_vencido(HOY, 3)
    assert not Video(fecha_grabacion=datetime(2026, 8, 31, 9, 0)).esta_vencido(date(2026, 11, 29), 3)
    assert Video(fecha_grabacion=datetime(2026, 8, 31, 9, 0)).esta_vencido(date(2026, 11, 30), 3)


# ------------------------------------------------------------------ RF11: cálculo de alertas del monitor


def _monitor(ahora: datetime) -> tuple[MonitorServicios, SimpleNamespace]:
    contenedor = SimpleNamespace(
        config=SimpleNamespace(monitor_concurrencia=1, bateria_alerta=20, retraso_alerta_min=10),
        reloj=RelojSimulado(ahora),
    )
    return MonitorServicios(contenedor), contenedor  # type: ignore[arg-type]


def _causas(ahora: datetime, bateria: int = 80, sensores: dict | None = None) -> list[CausaAlerta]:
    monitor, contenedor = _monitor(ahora)
    dispositivo = robot(bateria)
    telemetria = TelemetriaDispositivo(
        "R-001", ahora, 4.638, -74.084, bateria, sensores or {"GPS": EstadoSensor.OK}, Fase.EN_RUTA
    )
    contexto = ContextoMonitor(
        sesion=None,  # type: ignore[arg-type]
        contenedor=contenedor,
        dispositivo=dispositivo,
        telemetria=telemetria,
        bitacora=BitacoraServicio(estado=EstadoServicio.EN_CURSO, hora_regreso=None),
        reserva=Reserva(fecha=HOY, hora_inicio=time(10, 0), duracion_estimada_min=30),
    )
    return [c.causa for c in monitor.evaluar_umbrales(contexto)]


def test_rf11_umbral_de_bateria() -> None:
    a_las_diez = datetime(2026, 11, 9, 10, 5)
    assert _causas(a_las_diez, bateria=19) == [CausaAlerta.BATERIA_BAJA]
    assert _causas(a_las_diez, bateria=20) == []


def test_rf11_sensor_en_falla() -> None:
    sensores = {"GPS": EstadoSensor.OK, "LIDAR": EstadoSensor.FALLA}
    assert _causas(datetime(2026, 11, 9, 10, 5), sensores=sensores) == [CausaAlerta.SENSOR_EN_FALLA]


def test_rf11_retraso_estrictamente_mayor_a_10_minutos() -> None:
    assert _causas(datetime(2026, 11, 9, 10, 40, 0)) == []  # fin 10:30 + 10 min exactos
    assert _causas(datetime(2026, 11, 9, 10, 40, 1)) == [CausaAlerta.RETRASO]
