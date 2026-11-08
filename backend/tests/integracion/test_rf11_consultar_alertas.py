"""RF11 — Consulta de alertas (las de servicio y las de mantenimiento comparten formato).

En la Fase 4 se agregan las pruebas de generación de alertas en el monitoreo; aquí se prueba la consulta
con alertas creadas directamente en la base.
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

import httpx

from app.alertas.modelos import AlertaMantenimiento, AlertaServicio, AtencionAlerta
from app.contenedor import Contenedor
from app.nucleo.enums import CausaAlerta, EstadoReserva, TipoDispositivo, TipoIncidencia
from app.servicios.modelos import BitacoraServicio
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_reserva, crear_ubicaciones


async def _alertas_de_ejemplo(contenedor: Contenedor, admin: Usuario, operador: Usuario) -> dict[str, int]:
    robot = await crear_dispositivo(contenedor, numero_serie="R-001")
    drone = await crear_dispositivo(contenedor, tipo=TipoDispositivo.DRONE, numero_serie="D-001")
    lugares = await crear_ubicaciones(contenedor)
    reserva = await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=contenedor.reloj.hoy(),
        hora_inicio=time(8, 0),
        estado=EstadoReserva.EN_CURSO,
    )
    async with contenedor.sesiones() as sesion:
        bitacora = BitacoraServicio(id_reserva=reserva.id_reserva, hora_salida=datetime(2026, 11, 9, 8, 0))
        sesion.add(bitacora)
        await sesion.flush()
        bateria = bitacora.registrar_incidencia(
            TipoIncidencia.BATERIA_BAJA, "Batería 19 %", datetime(2026, 11, 9, 8, 10), 4.639, -74.083
        )
        sensor = bitacora.registrar_incidencia(
            TipoIncidencia.SENSOR_EN_FALLA, "Sensor LIDAR en falla", datetime(2026, 11, 9, 8, 12)
        )
        sesion.add_all([bateria, sensor])
        await sesion.flush()
        alerta_bateria = AlertaServicio(
            id_dispositivo=robot.id_dispositivo,
            fecha_hora=datetime(2026, 11, 9, 8, 10),
            descripcion="R-001: batería 19 %",
            id_incidencia=bateria.id_incidencia,
            causa=CausaAlerta.BATERIA_BAJA,
        )
        alerta_sensor = AlertaServicio(
            id_dispositivo=robot.id_dispositivo,
            fecha_hora=datetime(2026, 11, 9, 8, 12),
            descripcion="R-001: sensor LIDAR en falla",
            id_incidencia=sensor.id_incidencia,
            causa=CausaAlerta.SENSOR_EN_FALLA,
        )
        alerta_mant = AlertaMantenimiento(
            id_dispositivo=drone.id_dispositivo,
            fecha_hora=datetime(2026, 11, 9, 6, 0),
            descripcion="D-001 requiere mantenimiento preventivo",
            dias_desde_ultimo=31,
            horas_desde_ultimo=Decimal("12.50"),
        )
        sesion.add_all([alerta_bateria, alerta_sensor, alerta_mant])
        await sesion.flush()
        sesion.add(
            AtencionAlerta(
                id_alerta=alerta_sensor.id_alerta,
                id_operador=operador.id_usuario,
                fecha_hora=datetime(2026, 11, 9, 8, 15),
                causa_revisada="Sensor sucio",
                observaciones="Se limpió",
            )
        )
        await sesion.commit()
        return {
            "bateria": alerta_bateria.id_alerta,
            "sensor": alerta_sensor.id_alerta,
            "mantenimiento": alerta_mant.id_alerta,
            "bitacora": bitacora.id_bitacora,
            "robot": robot.id_dispositivo,
        }


async def test_rf11_lista_alertas_de_servicio_y_mantenimiento(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, auth
) -> None:
    ids = await _alertas_de_ejemplo(contenedor, admin, operador)
    respuesta = await cliente.get("/api/alertas", headers=auth(operador))
    assert respuesta.status_code == 200
    items = respuesta.json()["items"]
    assert [a["id_alerta"] for a in items] == [ids["sensor"], ids["bateria"], ids["mantenimiento"]]

    bateria = items[1]
    assert bateria["tipo"] == "SERVICIO" and bateria["causa"] == "BATERIA_BAJA"
    assert bateria["numero_serie"] == "R-001"
    assert bateria["id_bitacora"] == ids["bitacora"]
    assert bateria["id_operador"] == operador.id_usuario
    assert (bateria["latitud"], bateria["longitud"]) == (4.639, -74.083)
    assert bateria["atendida"] is False and bateria["atencion"] is None
    assert bateria["fecha_hora"] == "2026-11-09T08:10:00-05:00"

    sensor = items[0]
    assert sensor["atendida"] is True
    assert sensor["atencion"]["causa_revisada"] == "Sensor sucio"
    assert sensor["atencion"]["operador"] == {"id_usuario": operador.id_usuario, "nombre": "Óscar Operador"}

    mantenimiento = items[2]
    assert mantenimiento["tipo"] == "MANTENIMIENTO" and mantenimiento["causa"] is None
    assert mantenimiento["atendida"] is None
    assert (mantenimiento["dias_desde_ultimo"], mantenimiento["horas_desde_ultimo"]) == (31, 12.5)


async def test_rf11_filtros_y_detalle(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, auth
) -> None:
    ids = await _alertas_de_ejemplo(contenedor, admin, operador)

    async def alertas(**params: object) -> list[int]:
        respuesta = await cliente.get("/api/alertas", params=params, headers=auth(admin))
        assert respuesta.status_code == 200
        return [a["id_alerta"] for a in respuesta.json()["items"]]

    assert await alertas(tipo="MANTENIMIENTO") == [ids["mantenimiento"]]
    assert await alertas(atendida="false") == [ids["bateria"]]  # solo aplica a las de servicio
    assert await alertas(atendida="true") == [ids["sensor"]]
    assert await alertas(id_dispositivo=ids["robot"]) == [ids["sensor"], ids["bateria"]]
    assert await alertas(desde="2026-11-10") == []

    detalle = await cliente.get(f"/api/alertas/{ids['bateria']}", headers=auth(operador))
    assert detalle.status_code == 200 and detalle.json()["causa"] == "BATERIA_BAJA"
    assert (await cliente.get("/api/alertas/999", headers=auth(operador))).status_code == 404
