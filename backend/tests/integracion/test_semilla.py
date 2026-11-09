"""RESTR01 — Datos semilla mínimos de la demo, y RNF03 — con esos datos, los listados responden en
menos de 3 s."""

from __future__ import annotations

import time

import httpx
from sqlalchemy import func, select, text

from app.contenedor import Contenedor
from app.dispositivos.modelos import Dispositivo
from app.nucleo.enums import EstadoReserva, EstadoServicio, RolUsuario, TipoDispositivo
from app.reservas.modelos import Reserva
from app.semilla import CONTRASENA_ADMIN, CONTRASENA_OPERADOR, CORREO_ADMIN, CORREO_OPERADOR, sembrar
from app.servicios.modelos import BitacoraServicio, RegistroTelemetria
from app.usuarios.modelos import Usuario
from app.videos.modelos import Video


async def test_restr01_la_semilla_carga_la_demo_y_es_idempotente(
    cliente: httpx.AsyncClient, contenedor: Contenedor
) -> None:
    resumen = await sembrar(contenedor)
    assert resumen.sembrada
    conteos = resumen.conteos
    assert (conteos["usuario"], conteos["dispositivo"], conteos["ubicacion"]) == (2, 6, 8)
    assert conteos["reserva"] == 5  # 3 terminadas y 2 programadas para mañana
    assert conteos["bitacora_servicio"] == 3 and conteos["video"] == 3
    assert conteos["registro_telemetria"] > 3 * 20
    assert conteos["alerta"] == 2 and conteos["incidencia"] == 2  # sensor y batería (RF11)

    async with contenedor.sesiones() as sesion:
        usuarios = {u.nombre: u for u in (await sesion.scalars(select(Usuario))).all()}
        assert set(usuarios) == {"Emily Bonilla", "Santiago Figueroa"}
        assert usuarios["Emily Bonilla"].rol == RolUsuario.ADMINISTRADOR
        assert usuarios["Santiago Figueroa"].rol == RolUsuario.OPERADOR
        assert await sesion.scalar(text("SELECT count(*) FROM registro_auditoria")) == 0  # la auditoría empieza vacía
        dispositivos = {d.numero_serie: d for d in (await sesion.scalars(select(Dispositivo))).all()}
        assert sum(d.tipo == TipoDispositivo.ROBOT for d in dispositivos.values()) == 4
        assert dispositivos["R-004"].sensores_en_falla() == ["LIDAR"]  # RF07
        assert dispositivos["R-003"].nivel_bateria < 30  # RF07
        # El historial no usa a R-004: con el LIDAR en falla, RF07 no lo deja reservar.
        assert (
            await sesion.scalar(
                select(func.count())
                .select_from(Reserva)
                .where(Reserva.id_dispositivo == dispositivos["R-004"].id_dispositivo)
            )
            == 0
        )
        for tabla in ("zona_operacion", "mantenimiento", "atencion_alerta", "alerta_mantenimiento"):
            assert await sesion.scalar(text(f"SELECT count(*) FROM {tabla}")) == 0, tabla
        assert (
            await sesion.scalar(
                select(func.count())
                .select_from(BitacoraServicio)
                .where(BitacoraServicio.estado != EstadoServicio.FINALIZADO)
            )
            == 0
        )
        programadas = (await sesion.scalars(select(Reserva).where(Reserva.estado == EstadoReserva.PROGRAMADA))).all()
        assert len(programadas) == 2 and {r.fecha.isoformat() for r in programadas} == {"2026-11-10"}
        vigente = await sesion.scalar(select(Video).limit(1))
        assert vigente is not None
        assert (await contenedor.almacenamiento.obtener(vigente.url))[4:8] == b"ftyp"
        fallas = await sesion.scalar(
            select(func.count()).select_from(RegistroTelemetria).where(RegistroTelemetria.nivel_bateria < 0)
        )
        assert fallas == 0

    # El usuario semilla puede entrar.
    login = await cliente.post("/api/auth/login", json={"correo": CORREO_ADMIN, "contrasena": CONTRASENA_ADMIN})
    assert login.status_code == 200
    operador = await cliente.post(
        "/api/auth/login", json={"correo": CORREO_OPERADOR, "contrasena": CONTRASENA_OPERADOR}
    )
    assert operador.status_code == 200

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
