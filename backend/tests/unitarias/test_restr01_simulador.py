"""RESTR01 — Simulador de dispositivos: misión, fases, batería, órdenes, código, eventos, video y reanudación.

Sin base de datos: el cargador es falso y el reloj es simulado (el simulador avanza solo cuando se le consulta).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.integraciones.dispositivo.carga import DatosDispositivo
from app.integraciones.dispositivo.interfaz import (
    ErrorDispositivo,
    Fase,
    OrdenInicio,
    Punto,
    Reanudacion,
    ResultadoEntrega,
    TipoEvento,
)
from app.integraciones.dispositivo.simulador import ApiDispositivoSimulada, Escenario
from app.nucleo.enums import EstadoDispositivo, EstadoSensor, TipoDispositivo, TipoOrden, TipoServicio
from app.nucleo.reloj import RelojSimulado

INICIO = datetime(2026, 11, 9, 10, 0)
BASE = Punto(4.638, -74.084, "Base de operaciones")
CAFETERIA = Punto(4.639, -74.083, "Cafetería")
RECTORIA = Punto(4.640, -74.082, "Rectoría")
COLISEO = Punto(4.641, -74.085, "Coliseo")


class CargadorFalso:
    def __init__(self) -> None:
        ok = EstadoSensor.OK
        self.dispositivos = {
            "R-1": DatosDispositivo("R-1", TipoDispositivo.ROBOT, 100, {"GPS": ok, "LIDAR": ok}),
            "D-1": DatosDispositivo("D-1", TipoDispositivo.DRONE, 100, {"GPS": ok, "IMU": ok}),
            "R-2": DatosDispositivo("R-2", TipoDispositivo.ROBOT, 50, {"GPS": ok}, EstadoDispositivo.EN_CARGA),
        }

    async def dispositivo(self, numero_serie: str) -> DatosDispositivo | None:
        return self.dispositivos.get(numero_serie)

    async def base(self) -> Punto | None:
        return BASE


@pytest.fixture
def reloj() -> RelojSimulado:
    return RelojSimulado(INICIO)


@pytest.fixture
def simulador(reloj: RelojSimulado) -> ApiDispositivoSimulada:
    return ApiDispositivoSimulada(reloj, CargadorFalso(), fraccion_recorrido=0.8)


def orden(tipo: TipoServicio = TipoServicio.PEDIDO_CAFETERIA, **cambios: object) -> OrdenInicio:
    datos: dict = {
        "id_reserva": 7,
        "tipo_servicio": tipo,
        "origen": CAFETERIA if tipo != TipoServicio.GRABACION_EVENTO else BASE,
        "destino": RECTORIA if tipo != TipoServicio.GRABACION_EVENTO else COLISEO,
        "inicio": INICIO,
        "duracion_estimada_min": 30,
    }
    datos.update(cambios)
    return OrdenInicio(**datos)


async def eventos(simulador: ApiDispositivoSimulada) -> list:
    encontrados = []
    while not simulador._eventos.empty():
        encontrados.append(await simulador.esperar_evento())
    return encontrados


async def test_restr01_dispositivo_nuevo_aparece_en_la_base_con_sus_datos(simulador: ApiDispositivoSimulada) -> None:
    t = await simulador.obtener_telemetria("R-1")
    assert (t.latitud, t.longitud, t.nivel_bateria) == (BASE.latitud, BASE.longitud, 100)
    assert t.estado_servicio == Fase.EN_BASE
    with pytest.raises(ErrorDispositivo):
        await simulador.obtener_telemetria("NO-EXISTE")


async def test_restr01_robot_recorre_base_origen_destino_base_en_el_80_por_ciento(
    simulador: ApiDispositivoSimulada, reloj: RelojSimulado
) -> None:
    """Sin RF24 el robot deja el pedido y vuelve: 30 min × 0,8 = 24 min de recorrido."""
    await simulador.enviar_orden_inicio("R-1", orden())
    reloj.avanzar(minutes=6)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.EN_RUTA
    reloj.avanzar(minutes=9)  # 10:15: ya pasó por el destino (mitad del recorrido)
    t = await simulador.obtener_telemetria("R-1")
    assert t.estado_servicio == Fase.RETORNANDO
    assert t.nivel_bateria == 85  # 1 % por minuto (escenario.json)
    assert await eventos(simulador) == []
    reloj.avanzar(minutes=10)  # 10:25
    t = await simulador.obtener_telemetria("R-1")
    assert (t.estado_servicio, t.latitud, t.longitud) == (Fase.EN_BASE, BASE.latitud, BASE.longitud)
    [llegada] = await eventos(simulador)
    assert llegada.tipo == TipoEvento.LLEGADA_BASE and llegada.fecha_hora == INICIO + timedelta(minutes=24)
    assert (await simulador.descargar_video("R-1"))[4:8] == b"ftyp"


async def test_restr01_drone_vuela_la_mitad_y_graba_la_otra_mitad(
    simulador: ApiDispositivoSimulada, reloj: RelojSimulado
) -> None:
    """Base → Coliseo → base: 12 min de vuelo (6 de ida) y 12 min grabando en el destino."""
    await simulador.enviar_orden_inicio("D-1", orden(TipoServicio.GRABACION_EVENTO))
    reloj.avanzar(minutes=7)
    t = await simulador.obtener_telemetria("D-1")
    assert (t.estado_servicio, t.latitud, t.longitud) == (Fase.EN_DESTINO, COLISEO.latitud, COLISEO.longitud)
    reloj.avanzar(minutes=12)  # 10:19
    assert (await simulador.obtener_telemetria("D-1")).estado_servicio == Fase.RETORNANDO
    reloj.avanzar(minutes=6)
    assert (await simulador.obtener_telemetria("D-1")).estado_servicio == Fase.EN_BASE
    [llegada] = await eventos(simulador)
    assert llegada.fecha_hora == INICIO + timedelta(minutes=24)


async def test_restr01_robot_espera_el_codigo_si_la_orden_lo_pide(
    simulador: ApiDispositivoSimulada, reloj: RelojSimulado
) -> None:
    await simulador.enviar_orden_inicio("R-1", orden(esperar_codigo=True))
    with pytest.raises(ErrorDispositivo, match="no está esperando"):
        await simulador.ingresar_codigo("R-1", "1234")
    reloj.avanzar(minutes=40)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.ESPERANDO_CODIGO

    await simulador.ingresar_codigo("R-1", "9999")
    [aviso] = await eventos(simulador)
    assert aviso.tipo == TipoEvento.CODIGO_INGRESADO
    assert await simulador.leer_codigo_entrega("R-1") == "9999"
    assert await simulador.leer_codigo_entrega("R-1") is None
    await simulador.confirmar_entrega("R-1", ResultadoEntrega.NO_CONFIRMADA)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.ESPERANDO_CODIGO

    await simulador.confirmar_entrega("R-1", ResultadoEntrega.CONFIRMADA)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.RETORNANDO
    reloj.avanzar(minutes=12)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.EN_BASE


async def test_restr01_parada_de_emergencia_y_retorno_a_base(
    simulador: ApiDispositivoSimulada, reloj: RelojSimulado
) -> None:
    with pytest.raises(ErrorDispositivo, match="no está en un servicio"):
        await simulador.enviar_orden("R-1", TipoOrden.RETORNO_BASE)
    await simulador.enviar_orden_inicio("R-1", orden())
    reloj.avanzar(minutes=3)
    await simulador.enviar_orden("R-1", TipoOrden.PARADA_EMERGENCIA)
    detenido = await simulador.obtener_telemetria("R-1")
    reloj.avanzar(minutes=20)
    sigue = await simulador.obtener_telemetria("R-1")
    assert sigue.estado_servicio == Fase.DETENIDO
    assert (sigue.latitud, sigue.longitud) == (detenido.latitud, detenido.longitud)

    await simulador.enviar_orden("R-1", TipoOrden.RETORNO_BASE)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.RETORNANDO
    reloj.avanzar(minutes=10)
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.EN_BASE
    assert [e.tipo for e in await eventos(simulador)] == [TipoEvento.LLEGADA_BASE]


async def test_restr01_pausa_desvio_y_controles(simulador: ApiDispositivoSimulada, reloj: RelojSimulado) -> None:
    await simulador.enviar_orden_inicio("R-1", orden())
    with pytest.raises(ErrorDispositivo, match="ya está en un servicio"):
        await simulador.enviar_orden_inicio("R-1", orden())
    reloj.avanzar(minutes=2)
    await simulador.pausar("R-1")
    antes = await simulador.obtener_telemetria("R-1")
    reloj.avanzar(minutes=30)
    despues = await simulador.obtener_telemetria("R-1")
    assert (despues.latitud, despues.longitud) == (antes.latitud, antes.longitud)
    assert despues.estado_servicio == Fase.EN_RUTA

    await simulador.desviar("R-1")
    fuera = await simulador.obtener_telemetria("R-1")
    assert fuera.latitud == pytest.approx(antes.latitud + simulador.escenario.desvio_salida_zona[0])
    await simulador.desviar("R-1", False)
    await simulador.fijar_bateria("R-1", 19)
    await simulador.fallar_sensor("R-1", "lidar")
    t = await simulador.obtener_telemetria("R-1")
    assert (t.latitud, t.nivel_bateria, t.sensores["LIDAR"]) == (antes.latitud, 19, EstadoSensor.FALLA)
    with pytest.raises(ErrorDispositivo, match="no tiene el sensor"):
        await simulador.fallar_sensor("R-1", "radar")

    simulador.desconectar("R-1")
    with pytest.raises(ErrorDispositivo, match="no responde"):
        await simulador.obtener_telemetria("R-1")


async def test_restr01_recarga_en_la_base_despues_de_un_servicio(
    simulador: ApiDispositivoSimulada, reloj: RelojSimulado
) -> None:
    await simulador.enviar_orden_inicio("R-1", orden())
    reloj.avanzar(minutes=24)
    assert (await simulador.obtener_telemetria("R-1")).nivel_bateria == 76
    reloj.avanzar(minutes=5)  # 2 % por minuto en la base
    assert (await simulador.obtener_telemetria("R-1")).nivel_bateria == 86
    # Uno que la base tiene EN_CARGA también se recarga; uno que nunca salió conserva su batería.
    await simulador.obtener_telemetria("R-2")
    reloj.avanzar(minutes=10)
    assert (await simulador.obtener_telemetria("R-2")).nivel_bateria == 70


async def test_restr01_reanuda_desde_el_ultimo_punto(simulador: ApiDispositivoSimulada, reloj: RelojSimulado) -> None:
    """Decisión P1: tras un reinicio, el robot sigue desde su último punto hacia lo que le faltaba."""
    punto = Punto(4.6385, -74.0835)  # a mitad de camino entre la base y la Cafetería
    reloj.fijar(INICIO + timedelta(minutes=10))
    datos = Reanudacion(INICIO, punto, INICIO + timedelta(minutes=3), Fase.EN_RUTA)
    await simulador.enviar_orden_inicio("R-1", orden(reanudacion=datos))
    t = await simulador.obtener_telemetria("R-1")
    assert (t.latitud, t.longitud, t.estado_servicio) == (punto.latitud, punto.longitud, Fase.EN_RUTA)
    reloj.avanzar(minutes=30)
    await simulador.obtener_telemetria("R-1")
    assert [e.tipo for e in await eventos(simulador)] == [TipoEvento.LLEGADA_BASE]

    # Si ya volvía, va directo a la base.
    reloj.avanzar(minutes=1)
    regreso = Reanudacion(INICIO, RECTORIA, INICIO + timedelta(minutes=13), Fase.RETORNANDO, regresando=True)
    await simulador.enviar_orden_inicio("R-1", orden(reanudacion=regreso))
    assert (await simulador.obtener_telemetria("R-1")).estado_servicio == Fase.RETORNANDO


def test_restr01_escenario_precargado() -> None:
    escenario = Escenario.cargar()
    assert escenario.probabilidad_falla_sensor_por_min == 0  # determinista por defecto
    assert escenario.video_muestra.stat().st_size <= 1_000_000
    assert escenario.puntos_intermedios(RECTORIA, CAFETERIA) == tuple(
        reversed(escenario.puntos_intermedios(CAFETERIA, RECTORIA))
    )
    assert escenario.puntos_intermedios(BASE, COLISEO) == ()  # sin ruta precargada: línea recta
