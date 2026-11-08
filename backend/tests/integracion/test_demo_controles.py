"""Controles de demo del núcleo (especificación, sección 9): solo administrador y solo con ``MODO_DEMO=true``."""

from __future__ import annotations

from datetime import datetime, time

import httpx
import pytest

from app.contenedor import Contenedor
from app.integraciones.dispositivo.interfaz import Fase
from app.nucleo.enums import EstadoSensor
from app.nucleo.reloj import RelojSimulado
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_reserva, crear_ubicaciones, simulador_de


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


async def test_demo_iniciar_ya_una_reserva_con_las_validaciones_del_inicio(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    reloj: RelojSimulado,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
) -> None:
    robot = await crear_dispositivo(contenedor)
    reserva = await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=reloj.hoy(),
        hora_inicio=time(15, 0),
    )
    url = f"/api/demo/reservas/{reserva.id_reserva}/iniciar"
    assert (await cliente.post(url, headers=auth(operador))).status_code == 403

    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, 10)
    no_apto = await cliente.post(url, headers=auth(admin))
    assert no_apto.status_code == 409 and no_apto.json()["error"]["codigo"] == "DISPOSITIVO_NO_APTO"

    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, 90)
    iniciada = await cliente.post(url, headers=auth(admin))  # son las 08:00: no espera a las 15:00
    assert iniciada.status_code == 200
    assert iniciada.json() == {"resultado": "iniciada", "id_reserva": reserva.id_reserva, "id_bitacora": 1}
    otra_vez = await cliente.post(url, headers=auth(admin))
    assert otra_vez.status_code == 409 and "no está programada" in otra_vez.json()["error"]["mensaje"]
    assert (await cliente.post("/api/demo/reservas/999/iniciar", headers=auth(admin))).status_code == 404

    contenedor.config = contenedor.config.model_copy(update={"modo_demo": False})
    assert (await cliente.post(url, headers=auth(admin))).status_code == 404


async def test_demo_eventos_del_dispositivo_simulado(
    cliente: httpx.AsyncClient, contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, auth
) -> None:
    robot = await crear_dispositivo(contenedor, numero_serie="R-050")
    url = f"/api/demo/dispositivos/{robot.id_dispositivo}/eventos"
    simulador = simulador_de(contenedor)

    bateria = await cliente.post(url, json={"tipo": "BATERIA", "nivel": 19}, headers=auth(admin))
    assert bateria.status_code == 200
    assert bateria.json() == {
        "id_dispositivo": robot.id_dispositivo,
        "numero_serie": "R-050",
        "tipo": "BATERIA",
        "mensaje": "Batería de R-050 fijada en 19 %.",
    }
    assert (await cliente.post(url, json={"tipo": "falla_sensor", "sensor": "gps"}, headers=auth(admin))).is_success
    telemetria = await simulador.obtener_telemetria("R-050")
    assert telemetria.nivel_bateria == 19 and telemetria.sensores["GPS"] == EstadoSensor.FALLA
    assert (await cliente.post(url, json={"tipo": "REPARAR_SENSOR", "sensor": "GPS"}, headers=auth(admin))).is_success
    assert (await simulador.obtener_telemetria("R-050")).sensores["GPS"] == EstadoSensor.OK

    sin_nivel = await cliente.post(url, json={"tipo": "BATERIA"}, headers=auth(admin))
    assert sin_nivel.status_code == 422
    sin_sensor = await cliente.post(url, json={"tipo": "FALLA_SENSOR", "sensor": "radar"}, headers=auth(admin))
    assert sin_sensor.status_code == 409
    # Sin el módulo RF25, salir de la zona no está disponible.
    zona = await cliente.post(url, json={"tipo": "SALIR_DE_ZONA"}, headers=auth(admin))
    assert zona.status_code == 422 and "PAUSAR" in zona.json()["error"]["mensaje"]
    assert (
        await cliente.post("/api/demo/dispositivos/999/eventos", json={"tipo": "PAUSAR"}, headers=auth(admin))
    ).status_code == 404

    pausa = await cliente.post(url, json={"tipo": "PAUSAR"}, headers=auth(admin))
    assert pausa.json()["mensaje"] == "R-050 en pausa."
    assert (await cliente.post(url, json={"tipo": "REANUDAR"}, headers=auth(admin))).is_success
    assert (await simulador.obtener_telemetria("R-050")).estado_servicio == Fase.EN_BASE


async def test_demo_ejecutar_tareas(
    cliente: httpx.AsyncClient, contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, operador: Usuario, auth
) -> None:
    await crear_dispositivo(contenedor)
    monitoreo = await cliente.post("/api/demo/tareas/monitoreo/ejecutar", headers=auth(admin))
    assert monitoreo.json() == {"tarea": "monitoreo", "resultado": {"dispositivos": 1}}
    inicio = await cliente.post("/api/demo/tareas/iniciar-reservas/ejecutar", headers=auth(admin))
    assert inicio.json() == {"tarea": "iniciar-reservas", "resultado": {}}
    subidas = await cliente.post("/api/demo/tareas/reintento-subidas/ejecutar", headers=auth(admin))
    assert subidas.json()["resultado"] == {"subidos": 0, "pendientes": 0}
    # Una tarea de un módulo apagado (RF16) no existe en la entrega 1.
    rf16 = await cliente.post("/api/demo/tareas/mantenimiento-preventivo/ejecutar", headers=auth(admin))
    assert rf16.status_code == 404
    assert (await cliente.post("/api/demo/tareas/monitoreo/ejecutar", headers=auth(operador))).status_code == 403
    assert reloj.ahora() == datetime(2026, 11, 9, 8, 0)
