"""RNF10 — Se pueden registrar hasta 20 dispositivos sin cambiar el código (nada está fijado a 6), y el
simulador y el monitoreo los atienden a todos.
"""

from __future__ import annotations

import time

import httpx

from app.contenedor import Contenedor
from app.nucleo.enums import TipoDispositivo
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_dispositivo, crear_ubicaciones


async def test_rnf10_registra_veinte_dispositivos_y_aparecen_en_el_inventario(
    cliente: httpx.AsyncClient, admin: Usuario, auth
) -> None:
    for numero in range(1, 21):
        datos = (
            {"tipo": "ROBOT", "numero_serie": f"R-{numero:03d}", "modelo": "Rover", "capacidad_carga_kg": 5}
            if numero % 2
            else {"tipo": "DRONE", "numero_serie": f"D-{numero:03d}", "modelo": "Halcón", "autonomia_vuelo_min": 25}
        )
        respuesta = await cliente.post("/api/dispositivos", json=datos, headers=auth(admin))
        assert respuesta.status_code == 201, respuesta.text

    inventario = await cliente.get("/api/dispositivos", params={"limite": 50}, headers=auth(admin))
    assert inventario.json()["total"] == 20
    assert len(inventario.json()["items"]) == 20


async def test_rnf10_el_monitoreo_atiende_veinte_dispositivos_en_un_ciclo(
    cliente: httpx.AsyncClient, contenedor: Contenedor, operador: Usuario, auth
) -> None:
    await crear_ubicaciones(contenedor)
    for numero in range(20):
        await crear_dispositivo(contenedor, tipo=TipoDispositivo.ROBOT if numero % 2 else TipoDispositivo.DRONE)
    inicio = time.perf_counter()
    assert await contenedor.monitor.actualizar_monitoreo() == 20
    assert time.perf_counter() - inicio < contenedor.config.intervalo_monitoreo_seg
    foto = (await cliente.get("/api/monitoreo", headers=auth(operador))).json()
    assert len(foto["dispositivos"]) == 20
    assert all(d["telemetria"] is not None for d in foto["dispositivos"])
    assert len(contenedor.bus.historial(tipo="telemetria")) == 20
