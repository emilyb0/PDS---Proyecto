"""RF04 — Consultar inventario con filtros por tipo y estado."""

from __future__ import annotations

from datetime import datetime

import httpx

from app.contenedor import Contenedor
from app.nucleo.enums import EstadoDispositivo, EstadoReserva, TipoDispositivo
from app.servicios.modelos import BitacoraServicio
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_reserva, crear_ubicaciones


async def _inventario_de_ejemplo(contenedor: Contenedor) -> None:
    hoy = contenedor.reloj.hoy()
    await crear_dispositivo(contenedor, numero_serie="R-001", nivel_bateria=87)
    await crear_dispositivo(contenedor, numero_serie="R-002", estado=EstadoDispositivo.EN_CARGA, nivel_bateria=25)
    await crear_dispositivo(contenedor, numero_serie="R-003", sensores_en_falla=("LIDAR",))
    await crear_dispositivo(
        contenedor, numero_serie="R-004", estado=EstadoDispositivo.FUERA_DE_SERVICIO, fecha_baja=hoy
    )
    await crear_dispositivo(contenedor, tipo=TipoDispositivo.DRONE, numero_serie="D-001")
    await crear_dispositivo(
        contenedor, tipo=TipoDispositivo.DRONE, numero_serie="D-002", estado=EstadoDispositivo.EN_MANTENIMIENTO
    )


async def test_rf04_lista_todo_el_inventario_incluidos_los_dados_de_baja(
    cliente: httpx.AsyncClient, contenedor: Contenedor, operador: Usuario, auth
) -> None:
    await _inventario_de_ejemplo(contenedor)
    respuesta = await cliente.get("/api/dispositivos", headers=auth(operador))  # el operador también consulta
    assert respuesta.status_code == 200
    pagina = respuesta.json()
    assert pagina["total"] == 6
    por_serie = {d["numero_serie"]: d for d in pagina["items"]}
    assert list(por_serie) == ["R-001", "R-002", "R-003", "R-004", "D-001", "D-002"]
    assert por_serie["R-001"]["nivel_bateria"] == 87
    assert por_serie["R-003"]["sensores_en_falla"] == ["LIDAR"]
    assert por_serie["R-004"]["estado"] == "FUERA_DE_SERVICIO" and por_serie["R-004"]["dado_de_baja"] is True
    assert {"tipo", "modelo", "estado"} <= set(por_serie["D-001"])


async def test_rf04_filtra_por_tipo_por_estado_y_pagina(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, auth
) -> None:
    await _inventario_de_ejemplo(contenedor)

    async def series(**params: object) -> list[str]:
        respuesta = await cliente.get("/api/dispositivos", params=params, headers=auth(admin))
        assert respuesta.status_code == 200
        return [d["numero_serie"] for d in respuesta.json()["items"]]

    assert await series(tipo="DRONE") == ["D-001", "D-002"]
    assert await series(estado="EN_CARGA") == ["R-002"]
    assert await series(tipo="ROBOT", estado="DISPONIBLE") == ["R-001", "R-003"]
    assert await series(tipo="DRONE", estado="EN_CARGA") == []
    assert await series(limite=2, desplazamiento=2) == ["R-003", "R-004"]
    invalido = await cliente.get("/api/dispositivos", params={"estado": "ROTO"}, headers=auth(admin))
    assert invalido.status_code == 422


async def test_rf04_detalle_con_sensores_y_servicio_activo(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, auth
) -> None:
    robot = await crear_dispositivo(contenedor, sensores_en_falla=("Ultrasonido",))
    lugares = await crear_ubicaciones(contenedor)
    reserva = await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=robot,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=contenedor.reloj.hoy(),
        hora_inicio=datetime(2026, 11, 9, 8, 0).time(),
        estado=EstadoReserva.EN_CURSO,
    )
    async with contenedor.sesiones() as sesion:
        bitacora = BitacoraServicio(id_reserva=reserva.id_reserva, hora_salida=contenedor.reloj.ahora())
        sesion.add(bitacora)
        await sesion.commit()

    respuesta = await cliente.get(f"/api/dispositivos/{robot.id_dispositivo}", headers=auth(operador))
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [(s["nombre"], s["estado"]) for s in cuerpo["sensores"]] == [
        ("GPS", "OK"),
        ("Cámara", "OK"),
        ("LIDAR", "OK"),
        ("Ultrasonido", "FALLA"),
    ]
    assert cuerpo["servicio_activo"] == {
        "id_bitacora": bitacora.id_bitacora,
        "id_reserva": reserva.id_reserva,
        "estado": "EN_CURSO",
    }
    assert cuerpo["ultima_telemetria"] is None
    assert "mantenimiento_abierto" not in cuerpo  # eso lo muestra el módulo RF15

    assert (await cliente.get("/api/dispositivos/999", headers=auth(admin))).status_code == 404
