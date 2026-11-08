"""RF11 — Generar alertas de servicio: batería < 20 %, sensor en falla y retraso > 10 min, sin duplicados.

Cada alerta queda como incidencia (con ubicación), alerta y alerta de servicio en una transacción, y se publica
por SSE para el administrador y el operador.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest
from sqlalchemy import select

from app.alertas.modelos import AlertaServicio
from app.contenedor import Contenedor
from app.nucleo.enums import CausaAlerta, TipoIncidencia
from app.nucleo.reloj import RelojSimulado
from app.servicios.modelos import Incidencia
from app.servicios.monitor import MonitorServicios
from app.usuarios.modelos import Usuario
from tests.fabrica import ciclo, crear_dispositivo, crear_ubicaciones, servicio_en_curso, simulador_de


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


def causas(contenedor: Contenedor) -> list[str]:
    return [e.datos["causa"] for e in contenedor.bus.historial(tipo="alerta")]


@pytest.mark.parametrize(("bateria", "alerta"), [(19, True), (20, False)])
async def test_rf11_bateria_19_alerta_y_20_no(
    contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, bateria: int, alerta: bool
) -> None:
    robot, _, _ = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, bateria)
    await ciclo(contenedor)
    assert causas(contenedor) == (["BATERIA_BAJA"] if alerta else [])


async def test_rf11_sensor_en_falla_alerta_nombrando_el_sensor_con_ubicacion(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await simulador_de(contenedor).fallar_sensor(robot.numero_serie, "Ultrasonido")
    await ciclo(contenedor, minutes=1)
    [evento] = contenedor.bus.historial(tipo="alerta")
    assert evento.datos["tipo"] == "SERVICIO" and evento.datos["causa"] == "SENSOR_EN_FALLA"
    assert evento.datos["descripcion"] == f"{robot.numero_serie}: sensor Ultrasonido en falla"
    assert evento.datos["id_bitacora"] == id_bitacora and evento.datos["id_operador"] == operador.id_usuario
    assert evento.datos["atendida"] is False

    async with contenedor.sesiones() as sesion:
        incidencia = await sesion.scalar(select(Incidencia))
    assert incidencia is not None and incidencia.tipo == TipoIncidencia.SENSOR_EN_FALLA
    assert float(incidencia.latitud) == evento.datos["latitud"]
    assert float(incidencia.longitud) == evento.datos["longitud"]

    # La ve el administrador y también el operador.
    for usuario in (admin, operador):
        detalle = await cliente.get(f"/api/alertas/{evento.datos['id_alerta']}", headers=auth(usuario))
        assert detalle.status_code == 200 and detalle.json()["id_incidencia"] == incidencia.id_incidencia


async def test_rf11_retraso_de_mas_de_10_minutos_alerta_una_sola_vez(
    contenedor: Contenedor, reloj: RelojSimulado, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    robot, _, _ = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await simulador_de(contenedor).pausar(robot.numero_serie)  # se demora
    reloj.fijar(datetime(2026, 11, 9, 10, 40))  # fin 10:30 + 10 min exactos: todavía no
    await ciclo(contenedor)
    assert causas(contenedor) == []
    await ciclo(contenedor, seconds=5)
    assert causas(contenedor) == ["RETRASO"]
    descripcion = contenedor.bus.historial(tipo="alerta")[0].datos["descripcion"]
    assert descripcion == f"{robot.numero_serie}: 10 min de retraso sobre el fin estimado (10:30)"
    await ciclo(contenedor, minutes=5)
    await ciclo(contenedor, minutes=30)
    assert causas(contenedor) == ["RETRASO"]


async def test_rf11_sin_duplicados_pero_si_vuelve_a_ocurrir_alerta_de_nuevo(
    contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    robot, _, _ = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    simulador = simulador_de(contenedor)
    await simulador.fijar_bateria(robot.numero_serie, 19)
    await ciclo(contenedor, seconds=5)
    await ciclo(contenedor, seconds=5)  # sigue baja: no se repite
    await simulador.fijar_bateria(robot.numero_serie, 60)
    await ciclo(contenedor, seconds=5)  # se normalizó
    await simulador.fijar_bateria(robot.numero_serie, 15)
    await ciclo(contenedor, seconds=5)  # volvió a ocurrir
    assert causas(contenedor) == ["BATERIA_BAJA", "BATERIA_BAJA"]


async def test_rf11_despues_de_reiniciar_no_repite_las_alertas_activas(
    contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    robot, _, _ = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, 10)
    await ciclo(contenedor, seconds=5)
    contenedor.monitor = MonitorServicios(contenedor)  # se pierde lo que estaba en memoria
    await ciclo(contenedor, seconds=5)
    async with contenedor.sesiones() as sesion:
        guardadas = (await sesion.scalars(select(AlertaServicio.causa))).all()
    assert guardadas == [CausaAlerta.BATERIA_BAJA]


async def test_rf11_sin_servicio_en_curso_no_hay_alertas(contenedor: Contenedor, lugares: dict) -> None:
    robot = await crear_dispositivo(contenedor, sensores_en_falla=("GPS",))
    await simulador_de(contenedor).fijar_bateria(robot.numero_serie, 5)
    await ciclo(contenedor)
    assert causas(contenedor) == []
    assert contenedor.monitor.ultima_telemetria(robot.id_dispositivo) is not None
