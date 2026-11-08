"""RF09 — Monitorear dispositivos; RF10 — Actualizar el monitoreo en tiempo real por SSE (RNF02).

Las pruebas del flujo SSE levantan un servidor Uvicorn real (``tests/servidor.py``), porque ``ASGITransport``
espera a que la respuesta termine y un flujo SSE no termina.
"""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest
from sqlalchemy import update

from app.contenedor import Contenedor
from app.nucleo.enums import EstadoUsuario, TipoDispositivo
from app.usuarios.modelos import Usuario
from tests.fabrica import ciclo, crear_dispositivo, crear_ubicaciones, encabezados, servicio_en_curso, simulador_de
from tests.servidor import EventoRecibido, esperar, leer_sse, servidor_real


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


def _token(contenedor: Contenedor, usuario: Usuario) -> str:
    return encabezados(contenedor, usuario)["Authorization"].removeprefix("Bearer ")


async def test_rf09_monitoreo_refleja_la_ultima_telemetria_de_cada_dispositivo(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    robot, reserva, id_bitacora = await servicio_en_curso(
        contenedor, administrador=admin, operador=operador, lugares=lugares
    )
    drone = await crear_dispositivo(contenedor, tipo=TipoDispositivo.DRONE, nivel_bateria=64)
    await crear_dispositivo(contenedor, numero_serie="R-BAJA", fecha_baja=date(2026, 11, 1))

    antes = (await cliente.get("/api/monitoreo", headers=auth(operador))).json()
    assert [d["telemetria"] for d in antes["dispositivos"]] == [None, None]  # aún no hay lecturas

    await ciclo(contenedor, minutes=1)
    foto = (await cliente.get("/api/monitoreo", headers=auth(operador))).json()
    assert foto["intervalo_seg"] == 5 and foto["generado"] == "2026-11-09T10:01:00-05:00"
    por_serie = {d["numero_serie"]: d for d in foto["dispositivos"]}
    assert set(por_serie) == {robot.numero_serie, drone.numero_serie}  # el dado de baja no se monitorea
    en_servicio = por_serie[robot.numero_serie]
    assert en_servicio["servicio"] == {
        "id_bitacora": id_bitacora,
        "id_reserva": reserva.id_reserva,
        "tipo_servicio": "ENTREGA_DOCUMENTOS",
        "estado": "EN_CURSO",
        "hora_salida": "2026-11-09T10:00:00-05:00",
        "fin_estimado": "2026-11-09T10:30:00-05:00",
        "destino": {"id_ubicacion": lugares["Rectoría"].id_ubicacion, "nombre": "Rectoría"},
        "operador": {"id_usuario": operador.id_usuario, "nombre": operador.nombre},
    }
    telemetria = en_servicio["telemetria"]
    assert telemetria["id_bitacora"] == id_bitacora and telemetria["estado_servicio"] == "EN_RUTA"
    assert telemetria["nivel_bateria"] == 99 and telemetria["estado_dispositivo"] == "EN_SERVICIO"
    assert {s["nombre"] for s in telemetria["sensores"]} == {"GPS", "Cámara", "LIDAR", "Ultrasonido"}
    en_base = por_serie[drone.numero_serie]
    assert en_base["servicio"] is None
    assert en_base["telemetria"]["estado_servicio"] == "EN_BASE" and en_base["telemetria"]["id_bitacora"] is None
    assert en_base["telemetria"]["nivel_bateria"] == 64
    assert foto["alertas_abiertas"] == []
    assert (await cliente.get("/api/monitoreo")).status_code == 401


async def test_rf09_si_un_dispositivo_no_responde_se_sigue_con_los_demas(contenedor: Contenedor, lugares: dict) -> None:
    uno = await crear_dispositivo(contenedor)
    otro = await crear_dispositivo(contenedor)
    simulador = simulador_de(contenedor)
    await simulador.obtener_telemetria(uno.numero_serie)
    simulador.desconectar(uno.numero_serie)
    assert await contenedor.monitor.actualizar_monitoreo() == 1
    assert contenedor.monitor.ultima_telemetria(uno.id_dispositivo) is None
    assert contenedor.monitor.ultima_telemetria(otro.id_dispositivo) is not None


async def test_rf10_stream_sse_emite_telemetria_en_cada_ciclo_y_ping(
    app, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict
) -> None:
    contenedor.config = contenedor.config.model_copy(update={"sse_ping_seg": 0.2})
    robot, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    recibidos: list[EventoRecibido] = []
    comentarios: list[str] = []
    async with servidor_real(app) as url, httpx.AsyncClient(base_url=url, timeout=10) as http:
        cabeceras = {"Last-Event-ID": str(contenedor.bus.ultimo_id)}
        async with http.stream(
            "GET", "/api/monitoreo/stream", params={"token": _token(contenedor, operador)}, headers=cabeceras
        ) as respuesta:
            assert respuesta.status_code == 200
            assert respuesta.headers["content-type"].startswith("text/event-stream")
            lector = asyncio.create_task(leer_sse(respuesta, recibidos, comentarios))
            await ciclo(contenedor, seconds=5)
            await ciclo(contenedor, seconds=5)
            await esperar(lambda: len(recibidos) >= 2 and "ping" in comentarios)
            lector.cancel()
    assert [e.tipo for e in recibidos[:2]] == ["telemetria", "telemetria"]
    assert int(recibidos[1].id or 0) == int(recibidos[0].id or 0) + 1
    assert recibidos[0].datos["numero_serie"] == robot.numero_serie
    assert recibidos[0].datos["id_bitacora"] == id_bitacora
    assert recibidos[0].datos["fecha_hora"] == "2026-11-09T10:00:05-05:00"
    assert recibidos[1].datos["fecha_hora"] == "2026-11-09T10:00:10-05:00"


async def test_rf10_stream_reenvia_lo_que_falto_con_last_event_id(
    app, contenedor: Contenedor, operador: Usuario
) -> None:
    for i in range(5):
        contenedor.bus.publicar("prueba", {"n": i})
    recibidos: list[EventoRecibido] = []
    async with (
        servidor_real(app) as url,
        httpx.AsyncClient(base_url=url, timeout=10) as http,
        http.stream(
            "GET",
            "/api/monitoreo/stream",
            params={"token": _token(contenedor, operador)},
            headers={"Last-Event-ID": "3"},
        ) as respuesta,
    ):
        lector = asyncio.create_task(leer_sse(respuesta, recibidos, []))
        await esperar(lambda: len(recibidos) >= 2)
        lector.cancel()
    assert [(e.id, e.datos["n"]) for e in recibidos] == [("4", 3), ("5", 4)]


async def test_rf10_stream_exige_un_token_valido(cliente: httpx.AsyncClient) -> None:
    sin_token = await cliente.get("/api/monitoreo/stream")
    assert sin_token.status_code == 401 and sin_token.json()["error"]["codigo"] == "NO_AUTENTICADO"
    invalido = await cliente.get("/api/monitoreo/stream", params={"token": "no-es-un-jwt"})
    assert invalido.status_code == 401


async def test_rf10_stream_se_cierra_si_el_usuario_es_desactivado(
    app, contenedor: Contenedor, operador: Usuario
) -> None:
    """RF19: el usuario queda fuera de inmediato, también del tiempo real (se revisa cada SSE_REVALIDAR_SEG)."""
    contenedor.config = contenedor.config.model_copy(update={"sse_revalidar_seg": 0.2})
    async with (
        servidor_real(app) as url,
        httpx.AsyncClient(base_url=url, timeout=10) as http,
        http.stream("GET", "/api/monitoreo/stream", params={"token": _token(contenedor, operador)}) as respuesta,
    ):
        lector = asyncio.create_task(leer_sse(respuesta, [], []))
        await asyncio.sleep(0.3)
        assert not lector.done()
        async with contenedor.sesiones() as sesion:
            await sesion.execute(
                update(Usuario).where(Usuario.id_usuario == operador.id_usuario).values(estado=EstadoUsuario.INACTIVO)
            )
            await sesion.commit()
        await asyncio.wait_for(lector, timeout=5)  # el servidor cerró el flujo
