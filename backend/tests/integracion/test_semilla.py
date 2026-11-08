"""RESTR01 — Datos semilla de la demo (solo de la entrega 1), y RNF03 — con esos datos, los listados responden en
menos de 3 s."""

from __future__ import annotations

import time

import httpx
from sqlalchemy import func, select, text

from app.contenedor import Contenedor
from app.dispositivos.modelos import Dispositivo
from app.nucleo.enums import EstadoReserva, EstadoSensor, EstadoServicio, TipoDispositivo
from app.reservas.modelos import Reserva
from app.semilla import CONTRASENA_ADMIN, CORREO_ADMIN, sembrar
from app.servicios.modelos import BitacoraServicio, RegistroTelemetria
from app.videos.modelos import Video


async def test_restr01_la_semilla_carga_la_demo_y_es_idempotente(
    cliente: httpx.AsyncClient, contenedor: Contenedor
) -> None:
    resumen = await sembrar(contenedor)
    assert resumen.sembrada
    conteos = resumen.conteos
    assert (conteos["usuario"], conteos["dispositivo"], conteos["ubicacion"]) == (4, 6, 8)
    assert conteos["bitacora_servicio"] == 25 and conteos["video"] == 25
    assert conteos["reserva"] == 25 + 6  # el historial y 6 programadas (a las 08:00 aún caben las de hoy)
    assert conteos["registro_telemetria"] > 25 * 20
    assert conteos["alerta"] == 3 and conteos["incidencia"] == 3  # batería, sensor y retraso (RF11)

    async with contenedor.sesiones() as sesion:
        dispositivos = {d.numero_serie: d for d in (await sesion.scalars(select(Dispositivo))).all()}
        assert sum(d.tipo == TipoDispositivo.ROBOT for d in dispositivos.values()) == 4
        assert dispositivos["R-004"].sensores_en_falla() == ["LIDAR"]  # RF07
        assert dispositivos["R-003"].nivel_bateria < 30  # RF07
        # Solo datos de la entrega 1: nada de las tablas que usan los RF pendientes.
        for tabla in ("zona_operacion", "mantenimiento", "atencion_alerta", "alerta_mantenimiento"):
            assert await sesion.scalar(text(f"SELECT count(*) FROM {tabla}")) == 0, tabla
        assert (
            await sesion.scalar(select(func.count()).select_from(Video).where(Video.fecha_eliminacion.is_not(None)))
            == 0
        )
        assert (
            await sesion.scalar(
                select(func.count()).select_from(BitacoraServicio).where(BitacoraServicio.hora_entrega.is_not(None))
            )
            == 0
        )  # sin RF24 nadie confirma la entrega
        assert (
            await sesion.scalar(
                select(func.count())
                .select_from(BitacoraServicio)
                .where(BitacoraServicio.estado != EstadoServicio.FINALIZADO)
            )
            == 0
        )
        programadas = (await sesion.scalars(select(Reserva).where(Reserva.estado == EstadoReserva.PROGRAMADA))).all()
        assert {r.fecha.isoformat() for r in programadas} == {"2026-11-09", "2026-11-10"}
        vigente = await sesion.scalar(select(Video).limit(1))
        assert vigente is not None
        assert (await contenedor.almacenamiento.obtener(vigente.url))[4:8] == b"ftyp"
        fallas = await sesion.scalar(
            select(func.count()).select_from(RegistroTelemetria).where(RegistroTelemetria.nivel_bateria < 0)
        )
        assert fallas == 0
        assert EstadoSensor.FALLA in {s.estado for s in dispositivos["R-004"].sensores}

    # El usuario semilla puede entrar.
    login = await cliente.post("/api/auth/login", json={"correo": CORREO_ADMIN, "contrasena": CONTRASENA_ADMIN})
    assert login.status_code == 200

    # Idempotente: una segunda corrida no cambia nada; con --reiniciar vuelve a quedar igual.
    assert (await sembrar(contenedor)).sembrada is False
    otra = await sembrar(contenedor, reiniciar=True)
    assert otra.sembrada and otra.conteos == conteos


async def test_rnf03_con_los_datos_semilla_los_listados_responden_en_menos_de_3_segundos(
    cliente: httpx.AsyncClient, contenedor: Contenedor
) -> None:
    await sembrar(contenedor)
    token = (
        await cliente.post("/api/auth/login", json={"correo": CORREO_ADMIN, "contrasena": CONTRASENA_ADMIN})
    ).json()["token"]
    cabecera = {"Authorization": f"Bearer {token}"}
    for ruta in ("/api/dispositivos", "/api/reservas", "/api/bitacoras", "/api/alertas", "/api/monitoreo"):
        inicio = time.perf_counter()
        respuesta = await cliente.get(ruta, headers=cabecera)
        duracion = time.perf_counter() - inicio
        assert respuesta.status_code == 200, ruta
        assert duracion < 3, f"{ruta} tardó {duracion:.2f} s"
    ruta_bitacora = await cliente.get("/api/bitacoras/1/ruta", headers=cabecera)
    assert ruta_bitacora.status_code == 200 and len(ruta_bitacora.json()["puntos"]) > 10
