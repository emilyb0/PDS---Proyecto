"""RF05 — Crear reserva (núcleo: sin módulos; la sugerencia y el clima son RF22 y RF23)."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.auditoria.modelos import RegistroAuditoria
from app.contenedor import Contenedor
from app.nucleo.enums import EstadoDispositivo, EstadoUsuario, TipoDispositivo
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_ubicaciones, crear_usuario, datos_reserva


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


async def test_rf05_crea_reserva_de_robot_con_codigo_de_entrega(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor, numero_serie="R-001")
    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert respuesta.status_code == 201, respuesta.text
    r = respuesta.json()
    assert r["estado"] == "PROGRAMADA"
    assert (r["fecha"], r["hora_inicio"], r["hora_fin"]) == ("2026-11-09", "10:00", "10:30")
    assert (r["inicio"], r["fin"]) == ("2026-11-09T10:00:00-05:00", "2026-11-09T10:30:00-05:00")
    assert r["origen"]["nombre"] == "Cafetería" and r["destino"]["nombre"] == "Rectoría"
    assert r["dispositivo"]["numero_serie"] == "R-001"
    assert r["operador"] == {"id_usuario": operador.id_usuario, "nombre": "Óscar Operador"}
    assert r["administrador"]["id_usuario"] == admin.id_usuario
    assert len(r["codigo_entrega"]) == 4 and r["codigo_entrega"].isdigit()
    assert r["id_bitacora"] is None and r["advertencias"] == []

    # RNF09: la creación queda auditada.
    async with contenedor.sesiones() as sesion:
        filas = (
            await sesion.execute(
                select(RegistroAuditoria.accion, RegistroAuditoria.entidad, RegistroAuditoria.id_entidad)
            )
        ).all()
    assert [(a.value, e, i) for a, e, i in filas] == [("CREAR", "reserva", r["id_reserva"])]

    # El código de entrega solo lo ve el administrador.
    como_admin = await cliente.get(f"/api/reservas/{r['id_reserva']}", headers=auth(admin))
    como_operador = await cliente.get(f"/api/reservas/{r['id_reserva']}", headers=auth(operador))
    assert como_admin.json()["codigo_entrega"] == r["codigo_entrega"]
    assert como_operador.status_code == 200 and como_operador.json()["codigo_entrega"] is None


async def test_rf05_reserva_de_drone_sin_codigo(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    drone = await crear_dispositivo(contenedor, tipo=TipoDispositivo.DRONE)
    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, drone, operador), headers=auth(admin))
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["codigo_entrega"] is None
    assert respuesta.json()["tipo_servicio"] == "GRABACION_EVENTO"


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"hora_inicio": "07:59"}, "hora_inicio"),  # en el pasado (son las 08:00)
        ({"fecha": "2026-11-08"}, "hora_inicio"),
        ({"duracion_estimada_min": 0}, "duracion_estimada_min"),
        ({"duracion_estimada_min": 481}, "duracion_estimada_min"),
        ({"hora_inicio": "25:00"}, "hora_inicio"),
    ],
)
async def test_rf05_validaciones_de_entrada(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
    cambios: dict,
    campo: str,
) -> None:
    robot = await crear_dispositivo(contenedor)
    respuesta = await cliente.post(
        "/api/reservas", json=datos_reserva(lugares, robot, operador, **cambios), headers=auth(admin)
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["detalles"]["campos"][0]["campo"] == campo


async def test_rf05_se_acepta_el_minuto_en_curso(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    respuesta = await cliente.post(
        "/api/reservas", json=datos_reserva(lugares, robot, operador, hora_inicio="08:00"), headers=auth(admin)
    )
    assert respuesta.status_code == 201


async def test_rf05_origen_destino_y_operador_validos(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    cafeteria = lugares["Cafetería"].id_ubicacion
    inactivo = await crear_usuario(contenedor, estado=EstadoUsuario.INACTIVO)
    casos = [
        ({"id_destino": cafeteria}, "El origen y el destino deben ser distintos."),
        ({"id_origen": 999}, "La ubicación de origen no existe."),
        ({"id_destino": 999}, "La ubicación de destino no existe."),
        ({"id_operador": admin.id_usuario}, "El responsable debe ser un operador activo."),
        ({"id_operador": inactivo.id_usuario}, "El responsable debe ser un operador activo."),
    ]
    for cambios, mensaje in casos:
        respuesta = await cliente.post(
            "/api/reservas", json=datos_reserva(lugares, robot, operador, **cambios), headers=auth(admin)
        )
        assert respuesta.status_code == 422, cambios
        assert respuesta.json()["error"]["detalles"]["campos"][0]["mensaje"] == mensaje
    inexistente = await cliente.post(
        "/api/reservas", json=datos_reserva(lugares, robot, operador, id_dispositivo=999), headers=auth(admin)
    )
    assert inexistente.status_code == 404


async def test_rf05_tipo_de_dispositivo_segun_el_servicio(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    drone = await crear_dispositivo(contenedor, tipo=TipoDispositivo.DRONE)
    robot_graba = await cliente.post(
        "/api/reservas",
        headers=auth(admin),
        json=datos_reserva(lugares, robot, operador, tipo_servicio="GRABACION_EVENTO"),
    )
    drone_entrega = await cliente.post(
        "/api/reservas",
        headers=auth(admin),
        json=datos_reserva(lugares, drone, operador, tipo_servicio="ENTREGA_DOCUMENTOS"),
    )
    for respuesta in (robot_graba, drone_entrega):
        assert respuesta.status_code == 409
        assert respuesta.json()["error"]["codigo"] == "TIPO_DISPOSITIVO_INCORRECTO"
    assert "requiere un drone" in robot_graba.json()["error"]["mensaje"]


@pytest.mark.parametrize(
    ("estado", "baja", "texto"),
    [
        (EstadoDispositivo.EN_MANTENIMIENTO, False, "está en mantenimiento"),
        (EstadoDispositivo.FUERA_DE_SERVICIO, False, "está fuera de servicio"),
        (EstadoDispositivo.FUERA_DE_SERVICIO, True, "está dado de baja"),
    ],
)
async def test_rf05_dispositivo_no_asignable_por_estado(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
    estado: EstadoDispositivo,
    baja: bool,
    texto: str,
) -> None:
    robot = await crear_dispositivo(contenedor, estado=estado, fecha_baja=contenedor.reloj.hoy() if baja else None)
    respuesta = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DISPOSITIVO_NO_APTO"
    assert texto in respuesta.json()["error"]["mensaje"]


async def test_rf05_listar_con_filtros(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    otro = await crear_dispositivo(contenedor)
    for dispositivo, fecha, hora in (
        (robot, "2026-11-09", "11:00"),
        (robot, "2026-11-10", "09:00"),
        (otro, "2026-11-09", "10:00"),
    ):
        respuesta = await cliente.post(
            "/api/reservas",
            headers=auth(admin),
            json=datos_reserva(lugares, dispositivo, operador, fecha=fecha, hora_inicio=hora),
        )
        assert respuesta.status_code == 201

    async def ids(**params: object) -> list[tuple[str, str]]:
        respuesta = await cliente.get("/api/reservas", params=params, headers=auth(operador))
        return [(r["fecha"], r["hora_inicio"]) for r in respuesta.json()["items"]]

    assert await ids() == [("2026-11-09", "10:00"), ("2026-11-09", "11:00"), ("2026-11-10", "09:00")]
    assert await ids(fecha="2026-11-09") == [("2026-11-09", "10:00"), ("2026-11-09", "11:00")]
    assert await ids(id_dispositivo=robot.id_dispositivo) == [("2026-11-09", "11:00"), ("2026-11-10", "09:00")]
    assert await ids(estado="CANCELADA") == []
    assert (await cliente.get("/api/reservas/999", headers=auth(admin))).status_code == 404


async def test_rf05_rnf01_el_operador_no_crea_reservas(
    cliente: httpx.AsyncClient, contenedor: Contenedor, operador: Usuario, lugares: dict, auth
) -> None:
    robot = await crear_dispositivo(contenedor)
    respuesta = await cliente.post(
        "/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(operador)
    )
    assert respuesta.status_code == 403
