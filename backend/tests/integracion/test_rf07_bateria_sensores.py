"""RF07 — Validar batería y sensores consultando al dispositivo en ese momento (IApiDispositivo)."""

from __future__ import annotations

import httpx
import pytest

from app.contenedor import Contenedor
from app.dispositivos.modelos import Dispositivo
from app.integraciones.dispositivo.simulador import ApiDispositivoSimulada
from app.nucleo.enums import EstadoSensor
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_ubicaciones, datos_reserva


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


@pytest.mark.parametrize(("bateria", "esperado"), [(29, 409), (30, 201)])
async def test_rf07_bateria_29_rechaza_y_30_acepta(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
    bateria: int,
    esperado: int,
) -> None:
    robot = await crear_dispositivo(contenedor, nivel_bateria=bateria)
    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert respuesta.status_code == esperado
    if esperado == 409:
        error = respuesta.json()["error"]
        assert error["codigo"] == "DISPOSITIVO_NO_APTO"
        assert error["detalles"]["motivos"] == ["Batería 29 % (mínimo 30 %)"]


async def test_rf07_sensor_en_falla_rechaza_indicando_el_sensor(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor, nivel_bateria=20, sensores_en_falla=("LIDAR",))
    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["detalles"]["motivos"] == ["Batería 20 % (mínimo 30 %)", "Sensor LIDAR en falla"]


async def test_rf07_usa_el_estado_actual_del_dispositivo_y_lo_guarda(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    """La base dice 90 % y sensores bien, pero el dispositivo reporta 25 % y la cámara en falla en ese momento."""
    robot = await crear_dispositivo(contenedor, nivel_bateria=90)
    simulador = contenedor.api_dispositivo
    assert isinstance(simulador, ApiDispositivoSimulada)
    await simulador.fijar_bateria(robot.numero_serie, 25)
    await simulador.fallar_sensor(robot.numero_serie, "cámara")

    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["detalles"]["motivos"] == ["Batería 25 % (mínimo 30 %)", "Sensor Cámara en falla"]

    # La lectura queda guardada aunque la reserva se rechace (el inventario muestra el último nivel).
    async with contenedor.sesiones() as sesion:
        leido = await sesion.get(Dispositivo, robot.id_dispositivo)
    assert leido is not None and leido.nivel_bateria == 25
    assert {s.nombre: s.estado for s in leido.sensores}["Cámara"] == EstadoSensor.FALLA

    # Al repararse y recargarse, la misma reserva se acepta.
    await simulador.reparar_sensor(robot.numero_serie, "Cámara")
    await simulador.fijar_bateria(robot.numero_serie, 80)
    aceptada = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert aceptada.status_code == 201
