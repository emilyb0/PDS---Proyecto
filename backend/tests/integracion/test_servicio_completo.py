"""Servicio completo con el núcleo solo (entrega 1): reserva → inicio → monitoreo → alertas → cierre con video.

Recorre los pasos 12–63 del diagrama de secuencia por la API y las tareas reales (inicio automático, ciclos de
monitoreo y consumidor de eventos), con el reloj simulado. Sin módulos: el robot deja el pedido y vuelve (sin
RF24), y al cerrar no hay revisión preventiva (sin RF16).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.contenedor import Contenedor
from app.dispositivos.modelos import Dispositivo
from app.nucleo.enums import EstadoDispositivo
from app.nucleo.reloj import RelojSimulado
from app.usuarios.modelos import Usuario
from app.videos.modelos import Video
from tests.fabrica import ciclo, crear_dispositivo, crear_ubicaciones, datos_reserva, simulador_de


async def test_servicio_completo_reserva_inicio_monitoreo_alertas_y_cierre_con_video(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    reloj: RelojSimulado,
    admin: Usuario,
    operador: Usuario,
    auth,
) -> None:
    lugares = await crear_ubicaciones(contenedor)
    robot = await crear_dispositivo(contenedor, numero_serie="R-001")
    simulador = simulador_de(contenedor)
    bus = contenedor.bus

    # 1. Reserva (RF05–RF07): hoy de 10:00 a 10:30, de la Cafetería a la Rectoría.
    creada = await cliente.post("/api/reservas", json=datos_reserva(lugares, robot, operador), headers=auth(admin))
    assert creada.status_code == 201, creada.text
    id_reserva = creada.json()["id_reserva"]
    assert len(creada.json()["codigo_entrega"]) == 4

    # 2. Inicio automático (pasos 29–31, RF08): antes de la hora no pasa nada; a las 10:00 inicia.
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {}
    reloj.fijar(datetime(2026, 11, 9, 10, 0))
    assert await contenedor.monitor.iniciar_reservas_pendientes() == {"iniciada": 1}
    reserva = (await cliente.get(f"/api/reservas/{id_reserva}", headers=auth(operador))).json()
    assert reserva["estado"] == "EN_CURSO"
    id_bitacora = reserva["id_bitacora"]
    [iniciado] = bus.historial(tipo="servicio")
    assert iniciado.datos == {
        "id_bitacora": id_bitacora,
        "id_reserva": id_reserva,
        "id_dispositivo": robot.id_dispositivo,
        "evento": "INICIADO",
        "fecha_hora": "2026-11-09T10:00:00-05:00",
    }

    # 3. Monitoreo (RF09, RF10): cada ciclo guarda un punto y publica la telemetría.
    await ciclo(contenedor, minutes=2)
    foto = (await cliente.get("/api/monitoreo", headers=auth(operador))).json()
    [en_panel] = foto["dispositivos"]
    assert en_panel["estado"] == "EN_SERVICIO"
    assert en_panel["servicio"]["id_bitacora"] == id_bitacora
    assert en_panel["servicio"]["fin_estimado"] == "2026-11-09T10:30:00-05:00"
    assert en_panel["telemetria"]["estado_servicio"] == "EN_RUTA"
    assert en_panel["telemetria"]["nivel_bateria"] == 98
    assert en_panel["telemetria"]["fuera_de_zona"] is None  # sin el módulo RF25

    # 4. Alertas (RF11): batería baja y sensor en falla, sin duplicados.
    await simulador.fijar_bateria("R-001", 19)
    await ciclo(contenedor, seconds=5)
    await simulador.fallar_sensor("R-001", "LIDAR")
    await ciclo(contenedor, seconds=5)
    await ciclo(contenedor, seconds=5)  # siguen activas: no se repiten
    alertas = [e.datos for e in bus.historial(tipo="alerta")]
    assert [a["causa"] for a in alertas] == ["BATERIA_BAJA", "SENSOR_EN_FALLA"]
    assert alertas[0]["descripcion"] == "R-001: batería 19 % (mínimo 20 %)"
    assert alertas[1]["descripcion"] == "R-001: sensor LIDAR en falla"
    assert alertas[0]["id_operador"] == operador.id_usuario and alertas[0]["latitud"] is not None
    abiertas = (await cliente.get("/api/alertas", params={"atendida": "false"}, headers=auth(admin))).json()
    assert abiertas["total"] == 2

    # 5. Regreso: a las 10:15 ya dejó el pedido y vuelve (sin RF24 no espera código).
    await ciclo(contenedor, minutes=12)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(operador))).json()
    assert detalle["estado"] == "RETORNANDO"

    # 6. Cierre (pasos 55–63, RF08, RF12): llega a la base a las 10:24 y se guarda el video.
    await ciclo(contenedor, minutes=10)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO"
    assert detalle["hora_salida"] == "2026-11-09T10:00:00-05:00"
    assert detalle["hora_regreso"] == "2026-11-09T10:24:00-05:00"
    assert detalle["hora_entrega"] is None and detalle["entregado"] is False
    assert detalle["operador"]["id_usuario"] == operador.id_usuario
    assert detalle["reserva"]["estado"] == "FINALIZADA"
    assert detalle["horas_uso"] == 0.4
    assert [i["tipo"] for i in detalle["incidencias"]] == ["BATERIA_BAJA", "SENSOR_EN_FALLA"]
    assert all(i["id_alerta"] is not None for i in detalle["incidencias"])
    assert detalle["video"]["duracion_seg"] == 24 * 60
    assert detalle["video"]["fecha_grabacion"] == "2026-11-09T10:00:00-05:00"

    async with contenedor.sesiones() as sesion:
        video = await sesion.scalar(select(Video))
        dispositivo = await sesion.get(Dispositivo, robot.id_dispositivo)
    assert video is not None and video.url == f"local://videos/2026/11/bitacora-{id_bitacora}.mp4"
    contenido = await contenedor.almacenamiento.obtener(video.url)
    assert contenido[4:8] == b"ftyp"
    assert dispositivo is not None
    assert dispositivo.estado == EstadoDispositivo.EN_CARGA  # quedó con menos del 30 %
    assert dispositivo.horas_uso_desde_mant == Decimal("0.40")

    ruta = (await cliente.get(f"/api/bitacoras/{id_bitacora}/ruta", headers=auth(operador))).json()
    assert len(ruta["puntos"]) == 6  # uno por ciclo; el del cierre coincide con el último (D18)
    assert [p["estado_servicio"] for p in ruta["puntos"]][-2:] == ["RETORNANDO", "EN_BASE"]
    assert {s["nombre"] for s in ruta["puntos"][0]["sensores"]} == {"GPS", "Cámara", "LIDAR", "Ultrasonido"}

    finalizado = bus.historial(tipo="servicio")[-1]
    assert finalizado.datos["evento"] == "FINALIZADO" and finalizado.datos["id_bitacora"] == id_bitacora
    tipos = [e.tipo for e in bus.historial()]
    assert tipos[0] == "servicio" and tipos[-1] == "servicio"
    assert tipos.count("telemetria") == 6

    # 7. Recarga en la base: al llegar al 100 % vuelve a DISPONIBLE (decisión D5).
    await ciclo(contenedor, minutes=60)
    estado = (await cliente.get(f"/api/dispositivos/{robot.id_dispositivo}", headers=auth(admin))).json()
    assert (estado["estado"], estado["nivel_bateria"]) == ("DISPONIBLE", 100)
