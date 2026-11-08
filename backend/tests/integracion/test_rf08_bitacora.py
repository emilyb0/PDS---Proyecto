"""RF08 — Registrar bitácora del servicio: inicio automático, salida, regreso, ruta e incidencias.

Incluye las reglas del inicio (especificación 7.5): en espera si el dispositivo sigue en otro servicio, no se
inicia si no está apto, se cancela si la ventana termina, y la reanudación al reiniciar (decisión P1).
"""

from __future__ import annotations

from datetime import datetime, time

import httpx
import pytest
from sqlalchemy import update

from app.contenedor import Contenedor
from app.dispositivos.modelos import Dispositivo
from app.integraciones.dispositivo.carga import CargadorDesdeBD
from app.integraciones.dispositivo.simulador import ApiDispositivoSimulada
from app.nucleo.enums import EstadoDispositivo, TipoDispositivo
from app.nucleo.reloj import RelojSimulado
from app.servicios.monitor import MonitorServicios
from app.usuarios.modelos import Usuario
from tests.fabrica import (
    ciclo,
    crear_dispositivo,
    crear_reserva,
    crear_ubicaciones,
    servicio_en_curso,
    simulador_de,
)

HOY = datetime(2026, 11, 9).date()


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


async def test_rf08_al_iniciar_registra_salida_dispositivo_y_operador(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(operador))).json()
    assert detalle["estado"] == "EN_CURSO"
    assert detalle["hora_salida"] == "2026-11-09T10:00:00-05:00"
    assert detalle["hora_regreso"] is None
    assert detalle["dispositivo"]["numero_serie"] == robot.numero_serie
    assert detalle["operador"] == {"id_usuario": operador.id_usuario, "nombre": operador.nombre}
    assert detalle["reserva"]["codigo_entrega"] is None  # el operador no ve el código
    assert detalle["video"] is None and detalle["incidencias"] == []
    del_admin = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()
    assert del_admin["reserva"]["codigo_entrega"] == "1234"

    inventario = (await cliente.get(f"/api/dispositivos/{robot.id_dispositivo}", headers=auth(admin))).json()
    assert inventario["estado"] == "EN_SERVICIO"
    assert inventario["servicio_activo"]["id_bitacora"] == id_bitacora


async def test_rf08_robot_sin_rf24_deja_el_pedido_y_vuelve_sin_hora_de_entrega(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    _, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await ciclo(contenedor, minutes=13)
    assert (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()["estado"] == "RETORNANDO"
    await ciclo(contenedor, minutes=12)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["hora_entrega"] is None


async def test_rf08_espera_si_el_dispositivo_sigue_en_otro_servicio(
    contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    robot, _, primera = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    siguiente = await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=HOY,
        hora_inicio=time(10, 30),
    )
    await simulador_de(contenedor).pausar(robot.numero_serie)  # el primer servicio se demora
    reloj.fijar(datetime(2026, 11, 9, 10, 30))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"en_espera": 1}
    reloj.fijar(datetime(2026, 11, 9, 10, 30, 10))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"en_espera": 1}
    [aviso] = contenedor.bus.historial(tipo="servicio_en_espera")  # se avisa una sola vez
    assert aviso.datos["id_reserva"] == siguiente.id_reserva
    assert aviso.datos["motivo"] == f"El dispositivo {robot.numero_serie} sigue en el servicio de la reserva #1"

    await simulador_de(contenedor).pausar(robot.numero_serie, False)
    await ciclo(contenedor, minutes=24, seconds=5)  # el primero termina a las 10:54:10, dentro de la ventana
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"iniciada": 1}
    assert [e.datos["id_bitacora"] for e in contenedor.bus.historial(tipo="servicio")] == [primera, primera, 2]


async def test_rf08_no_inicia_si_el_dispositivo_no_esta_apto_y_avisa_una_vez(
    contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    robot = await crear_dispositivo(contenedor)
    reserva = await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=HOY,
        hora_inicio=time(10, 0),
    )
    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, 25)
    reloj.fijar(datetime(2026, 11, 9, 10, 0))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"no_iniciada": 1}
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"no_iniciada": 1}
    [aviso] = contenedor.bus.historial(tipo="servicio_no_iniciado")
    assert aviso.datos == {
        "id_reserva": reserva.id_reserva,
        "id_dispositivo": robot.id_dispositivo,
        "motivo": "Batería 25 % (mínimo 30 %)",
        "fecha_hora": "2026-11-09T10:00:00-05:00",
        "cancelada": False,
    }
    # Cuando vuelve a estar apto (por ejemplo, tras cargarlo), inicia dentro de su ventana.
    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, 80)
    reloj.fijar(datetime(2026, 11, 9, 10, 5))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"iniciada": 1}


async def test_rf08_si_la_ventana_termina_sin_iniciar_se_cancela(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    reloj: RelojSimulado,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
) -> None:
    robot = await crear_dispositivo(contenedor, numero_serie="R-777")
    reserva = await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=HOY,
        hora_inicio=time(10, 0),
    )
    async with contenedor.sesiones() as sesion:
        await sesion.execute(
            update(Dispositivo)
            .where(Dispositivo.id_dispositivo == robot.id_dispositivo)
            .values(estado=EstadoDispositivo.EN_MANTENIMIENTO)
        )
        await sesion.commit()
    reloj.fijar(datetime(2026, 11, 9, 10, 0))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"no_iniciada": 1}
    reloj.fijar(datetime(2026, 11, 9, 10, 30))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"cancelada": 1}
    cancelada = (await cliente.get(f"/api/reservas/{reserva.id_reserva}", headers=auth(admin))).json()
    assert cancelada["estado"] == "CANCELADA"
    assert cancelada["motivo_cambio"] == "No se inició: El dispositivo R-777 está en mantenimiento"
    ultimo = contenedor.bus.historial(tipo="servicio_no_iniciado")[-1]
    assert ultimo.datos["cancelada"] is True


async def test_rf08_si_el_dispositivo_no_responde_no_inicia(
    contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    robot = await crear_dispositivo(contenedor)
    await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=HOY,
        hora_inicio=time(10, 0),
    )
    simulador = simulador_de(contenedor)
    await simulador.obtener_telemetria(robot.numero_serie)
    simulador.desconectar(robot.numero_serie)
    reloj.fijar(datetime(2026, 11, 9, 10, 0))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"no_iniciada": 1}
    assert "no responde" in contenedor.bus.historial(tipo="servicio_no_iniciado")[0].datos["motivo"]


async def test_rf08_listado_filtros_y_ruta(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot, _, id_robot = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await ciclo(contenedor, minutes=25)  # termina el del robot
    drone, _, id_drone = await servicio_en_curso(
        contenedor,
        administrador=admin,
        operador=operador,
        lugares=lugares,
        tipo=TipoDispositivo.DRONE,
        hora_inicio=time(11, 0),
    )
    await ciclo(contenedor, minutes=1)

    todas = (await cliente.get("/api/bitacoras", headers=auth(operador))).json()
    assert [b["id_bitacora"] for b in todas["items"]] == [id_drone, id_robot]  # la más reciente primero
    assert todas["items"][1]["tiene_video"] is True and todas["items"][0]["tiene_video"] is False

    async def ids(**parametros: object) -> list[int]:
        respuesta = await cliente.get("/api/bitacoras", params=parametros, headers=auth(operador))
        return [b["id_bitacora"] for b in respuesta.json()["items"]]

    assert await ids(estado="FINALIZADO") == [id_robot]
    assert await ids(id_dispositivo=drone.id_dispositivo) == [id_drone]
    assert await ids(desde="2026-11-10") == []
    assert await ids(hasta="2026-11-09") == [id_drone, id_robot]
    invertido = await cliente.get(
        "/api/bitacoras", params={"desde": "2026-11-10", "hasta": "2026-11-09"}, headers=auth(operador)
    )
    assert invertido.status_code == 422

    ruta = (await cliente.get(f"/api/bitacoras/{id_drone}/ruta", headers=auth(operador))).json()
    [punto] = ruta["puntos"]
    assert punto["estado_servicio"] == "EN_RUTA" and len(punto["sensores"]) == 4
    assert (await cliente.get("/api/bitacoras/999", headers=auth(operador))).status_code == 404
    assert (await cliente.get("/api/bitacoras/999/ruta", headers=auth(operador))).status_code == 404
    assert (await cliente.get("/api/bitacoras")).status_code == 401
    assert robot.id_dispositivo != drone.id_dispositivo


async def test_rf08_al_reiniciar_reanuda_los_servicios_abiertos(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    """Decisión P1: el backend se reinicia a mitad del servicio; el robot sigue desde su último punto."""
    robot, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await ciclo(contenedor, minutes=3)

    # "Reinicio": simulador y monitor nuevos, sin nada en memoria.
    contenedor.api_dispositivo = ApiDispositivoSimulada(
        contenedor.reloj, CargadorDesdeBD(contenedor.sesiones, contenedor.config.base_ubicacion)
    )
    contenedor.monitor = MonitorServicios(contenedor)
    assert await contenedor.monitor.reanudar_servicios() == 1
    simulador = simulador_de(contenedor)
    assert simulador.en_mision(robot.numero_serie)
    t = await simulador.obtener_telemetria(robot.numero_serie)
    ruta = (await cliente.get(f"/api/bitacoras/{id_bitacora}/ruta", headers=auth(admin))).json()
    assert (t.latitud, t.longitud) == (ruta["puntos"][-1]["latitud"], ruta["puntos"][-1]["longitud"])

    await ciclo(contenedor, minutes=30)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["video"] is not None
