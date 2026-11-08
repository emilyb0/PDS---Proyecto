"""Formato único de error y traducción de errores de PostgreSQL (especificación, secciones 4 y 9)."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dispositivos.modelos import Robot
from app.nucleo.dependencias import Sesion
from app.nucleo.enums import TipoServicio
from app.nucleo.errores import (
    ErrorCruceHorario,
    ErrorDuplicado,
    ErrorNoEncontrado,
    ErrorReglaNegocio,
    traducir_error_bd,
)
from app.reservas.modelos import Reserva
from app.ubicaciones.modelos import Ubicacion
from app.usuarios.modelos import Usuario

HOY = date(2026, 11, 9)
AHORA = datetime(2026, 11, 9, 8, 0)


async def _error_de(sesion: AsyncSession, sql: str) -> DBAPIError:
    with pytest.raises(DBAPIError) as capturado:
        await sesion.execute(text(sql))
    await sesion.rollback()
    return capturado.value


async def _robot_y_ubicaciones(sesion: AsyncSession) -> tuple[Robot, Ubicacion, Ubicacion]:
    robot = Robot(numero_serie="R-001", modelo="Rover", capacidad_carga_kg=Decimal(5), fecha_registro=HOY)
    a = Ubicacion(nombre="A", latitud=Decimal(4), longitud=Decimal(-74))
    b = Ubicacion(nombre="B", latitud=Decimal(4), longitud=Decimal(-74))
    sesion.add_all([robot, a, b])
    await sesion.commit()
    return robot, a, b


async def test_traduce_unico_check_trigger_y_llave_foranea(sesion: AsyncSession) -> None:
    await _robot_y_ubicaciones(sesion)

    duplicado = traducir_error_bd(
        await _error_de(
            sesion,
            """
        INSERT INTO dispositivo (tipo, numero_serie, modelo, capacidad_carga_kg) VALUES ('ROBOT', 'R-001', 'x', 1)
    """,
        )
    )
    assert isinstance(duplicado, ErrorDuplicado)
    assert duplicado.mensaje == "Ya existe un dispositivo con ese número de serie."

    check = traducir_error_bd(
        await _error_de(
            sesion,
            """
        INSERT INTO dispositivo (tipo, numero_serie, modelo, capacidad_carga_kg, autonomia_vuelo_min)
        VALUES ('ROBOT', 'R-009', 'x', 1, 20)
    """,
        )
    )
    assert isinstance(check, ErrorReglaNegocio)
    assert "robot lleva capacidad de carga" in check.mensaje

    foranea = traducir_error_bd(
        await _error_de(
            sesion,
            """
        INSERT INTO sensor (id_dispositivo, nombre) VALUES (999, 'GPS')
    """,
        )
    )
    assert isinstance(foranea, ErrorNoEncontrado)


async def test_traduce_mensaje_del_trigger_y_exclusion(sesion: AsyncSession, admin: Usuario, operador: Usuario) -> None:
    robot, a, b = await _robot_y_ubicaciones(sesion)
    base = dict(
        id_administrador=admin.id_usuario,
        id_operador=operador.id_usuario,
        id_dispositivo=robot.id_dispositivo,
        id_origen=a.id_ubicacion,
        id_destino=b.id_ubicacion,
        tipo_servicio=TipoServicio.ENTREGA_DOCUMENTOS,
        fecha=HOY,
        duracion_estimada_min=30,
    )

    # Trigger fn_validar_reserva: el responsable debe ser operador (P0001 → REGLA_NEGOCIO con su mensaje).
    sesion.add(
        Reserva(
            **{**base, "id_operador": admin.id_usuario},
            hora_inicio=time(9, 0),
            codigo_entrega="1111",
            fecha_creacion=AHORA,
        )
    )
    with pytest.raises(DBAPIError) as capturado:
        await sesion.flush()
    await sesion.rollback()
    trigger = traducir_error_bd(capturado.value)
    assert isinstance(trigger, ErrorReglaNegocio)
    assert trigger.mensaje == "El responsable de la reserva debe ser un operador activo (RF05)"

    # EXCLUDE ex_reserva_cruce (23P01 → CRUCE_HORARIO).
    sesion.add(Reserva(**base, hora_inicio=time(10, 0), codigo_entrega="1111", fecha_creacion=AHORA))
    await sesion.commit()
    sesion.add(Reserva(**base, hora_inicio=time(10, 15), codigo_entrega="2222", fecha_creacion=AHORA))
    with pytest.raises(DBAPIError) as capturado:
        await sesion.flush()
    await sesion.rollback()
    assert isinstance(traducir_error_bd(capturado.value), ErrorCruceHorario)


async def test_error_de_bd_en_una_ruta_sale_con_el_formato_unico(app, cliente: httpx.AsyncClient) -> None:
    async def ruta_que_duplica(sesion: Sesion) -> None:
        for _ in range(2):
            await sesion.execute(text("INSERT INTO ubicacion (nombre, latitud, longitud) VALUES ('Repetida', 4, -74)"))

    app.add_api_route("/prueba/duplicado", ruta_que_duplica, methods=["POST"])
    respuesta = await cliente.post("/prueba/duplicado")
    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "error": {
            "codigo": "DUPLICADO",
            "mensaje": "Ya existe una ubicación con ese nombre.",
            "detalles": None,
        }
    }


async def test_validacion_422_en_espanol_con_campos(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.post("/api/auth/login", json={"correo": "a@campus.edu.co"})
    assert respuesta.status_code == 422
    error = respuesta.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert error["detalles"]["campos"] == [{"campo": "contrasena", "mensaje": "Campo obligatorio."}]


async def test_ruta_inexistente_404_con_formato(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "NO_ENCONTRADO"


async def test_error_inesperado_500_sin_detalles_internos(app) -> None:
    async def ruta_que_falla() -> None:
        raise RuntimeError("detalle interno que no debe salir")

    app.add_api_route("/prueba/falla", ruta_que_falla)
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        respuesta = await cliente.get("/prueba/falla")
    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "error": {"codigo": "ERROR_INTERNO", "mensaje": "Ocurrió un error interno.", "detalles": None}
    }
