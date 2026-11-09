"""RF06 — Validar cruce de horarios, incluida la concurrencia (la restricción EXCLUDE es la última barrera)."""

from __future__ import annotations

import asyncio
from datetime import time

import httpx
import pytest
from sqlalchemy import func, select

from app.contenedor import Contenedor
from app.nucleo.enums import EstadoReserva
from app.reservas.gestor_reservas import GestorReservas
from app.reservas.modelos import Reserva
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_reserva, crear_ubicaciones, datos_reserva


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


async def _cantidad_reservas(contenedor: Contenedor) -> int:
    async with contenedor.sesiones() as sesion:
        return await sesion.scalar(select(func.count()).select_from(Reserva)) or 0


async def test_rf06_cruce_rechazado_mostrando_la_reserva_en_conflicto(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor, numero_serie="R-002")
    primera = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    id_primera = primera.json()["id_reserva"]

    cruzada = await cliente.post(
        "/api/reservas", headers=auth(admin), json=datos_reserva(lugares, robot, operador, hora_inicio="10:15")
    )
    assert cruzada.status_code == 409
    error = cruzada.json()["error"]
    assert error["codigo"] == "CRUCE_HORARIO"
    assert error["mensaje"] == f"El dispositivo R-002 ya tiene la reserva #{id_primera} el 09/11/2026 de 10:00 a 10:30."
    assert error["detalles"]["reserva_en_conflicto"] == {
        "id_reserva": id_primera,
        "fecha": "2026-11-09",
        "hora_inicio": "10:00",
        "hora_fin": "10:30",
        "tipo_servicio": "PEDIDO_CAFETERIA",
        "estado": "PROGRAMADA",
        "operador": {"id_usuario": operador.id_usuario, "nombre": "Óscar Operador"},
    }


async def test_rf06_reservas_contiguas_y_otros_dispositivos_permitidos(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    otro = await crear_dispositivo(contenedor)
    for dispositivo, hora in ((robot, "10:00"), (robot, "10:30"), (robot, "09:30"), (otro, "10:00")):
        respuesta = await cliente.post(
            "/api/reservas", headers=auth(admin), json=datos_reserva(lugares, dispositivo, operador, hora_inicio=hora)
        )
        assert respuesta.status_code == 201, (hora, respuesta.text)
    assert await _cantidad_reservas(contenedor) == 4


async def test_rf06_las_canceladas_y_finalizadas_no_ocupan_el_horario(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    for estado in (EstadoReserva.CANCELADA, EstadoReserva.FINALIZADA):
        await crear_reserva(
            contenedor,
            administrador=admin,
            operador=operador,
            dispositivo=robot,
            origen=lugares["Cafetería"],
            destino=lugares["Rectoría"],
            fecha=contenedor.reloj.hoy(),
            hora_inicio=time(10, 0),
            estado=estado,
        )
    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert respuesta.status_code == 201

    en_curso = await crear_dispositivo(contenedor)
    await crear_reserva(
        contenedor,
        administrador=admin,
        operador=operador,
        dispositivo=en_curso,
        origen=lugares["Cafetería"],
        destino=lugares["Rectoría"],
        fecha=contenedor.reloj.hoy(),
        hora_inicio=time(9, 50),
        estado=EstadoReserva.EN_CURSO,
    )
    choca = await cliente.post("/api/reservas", json=datos_reserva(lugares, en_curso, operador), headers=auth(admin))
    assert choca.status_code == 409 and choca.json()["error"]["codigo"] == "CRUCE_HORARIO"


async def test_rf06_dos_creaciones_simultaneas_dan_un_201_y_un_409(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    datos = datos_reserva(lugares, robot, operador)
    respuestas = await asyncio.gather(
        cliente.post("/api/reservas", json=datos, headers=auth(admin)),
        cliente.post("/api/reservas", json=datos, headers=auth(admin)),
    )
    assert sorted(r.status_code for r in respuestas) == [201, 409]
    rechazada = next(r for r in respuestas if r.status_code == 409)
    assert rechazada.json()["error"]["codigo"] == "CRUCE_HORARIO"
    assert await _cantidad_reservas(contenedor) == 1


async def test_rf06_la_restriccion_exclude_es_la_ultima_barrera(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si las dos peticiones pasan la validación del servicio a la vez, la base (23P01) da el 409 con el conflicto."""

    async def sin_validacion(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(GestorReservas, "validar_cruce_horario", sin_validacion)
    robot = await crear_dispositivo(contenedor, numero_serie="R-007")
    datos = datos_reserva(lugares, robot, operador)
    respuestas = await asyncio.gather(
        cliente.post("/api/reservas", json=datos, headers=auth(admin)),
        cliente.post("/api/reservas", json={**datos, "hora_inicio": "10:10"}, headers=auth(admin)),
    )
    assert sorted(r.status_code for r in respuestas) == [201, 409]
    ganadora = next(r for r in respuestas if r.status_code == 201).json()
    error = next(r for r in respuestas if r.status_code == 409).json()["error"]
    assert error["codigo"] == "CRUCE_HORARIO"
    assert error["detalles"]["reserva_en_conflicto"]["id_reserva"] == ganadora["id_reserva"]
    assert await _cantidad_reservas(contenedor) == 1
