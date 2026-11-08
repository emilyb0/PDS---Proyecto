"""RF01 — Registrar dispositivo."""

from __future__ import annotations

import httpx
import pytest

from app.usuarios.modelos import Usuario

ROBOT = {"tipo": "ROBOT", "numero_serie": "r-010", "modelo": "Rover Mk2", "capacidad_carga_kg": 5.5}
DRONE = {"tipo": "DRONE", "numero_serie": "D-010", "modelo": "Halcón X4", "autonomia_vuelo_min": 25}


async def test_rf01_registra_robot_disponible_con_sensores_por_defecto(
    cliente: httpx.AsyncClient, admin: Usuario, auth
) -> None:
    respuesta = await cliente.post("/api/dispositivos", json=ROBOT, headers=auth(admin))
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "DISPONIBLE"
    assert cuerpo["numero_serie"] == "R-010"  # se guarda en mayúsculas
    assert cuerpo["capacidad_carga_kg"] == 5.5
    assert cuerpo["autonomia_vuelo_min"] is None
    assert cuerpo["fecha_registro"] == "2026-11-09"
    assert cuerpo["nivel_bateria"] == 100
    assert [s["nombre"] for s in cuerpo["sensores"]] == ["GPS", "Cámara", "LIDAR", "Ultrasonido"]
    assert all(s["estado"] == "OK" for s in cuerpo["sensores"])
    assert cuerpo["sensores_en_falla"] == []
    assert cuerpo["dado_de_baja"] is False

    # Queda en el inventario.
    inventario = await cliente.get("/api/dispositivos", headers=auth(admin))
    assert [d["numero_serie"] for d in inventario.json()["items"]] == ["R-010"]


async def test_rf01_registra_drone_con_sensores_propios_y_estado_inicial(
    cliente: httpx.AsyncClient, admin: Usuario, auth
) -> None:
    datos = {**DRONE, "estado": "EN_CARGA", "sensores": ["GPS", "Cámara térmica"]}
    respuesta = await cliente.post("/api/dispositivos", json=datos, headers=auth(admin))
    assert respuesta.status_code == 201
    assert respuesta.json()["estado"] == "EN_CARGA"
    assert [s["nombre"] for s in respuesta.json()["sensores"]] == ["GPS", "Cámara térmica"]

    por_defecto = await cliente.post("/api/dispositivos", json={**DRONE, "numero_serie": "D-011"}, headers=auth(admin))
    assert [s["nombre"] for s in por_defecto.json()["sensores"]] == ["GPS", "Cámara", "IMU", "Barómetro"]


async def test_rf01_numero_de_serie_duplicado_da_409(cliente: httpx.AsyncClient, admin: Usuario, auth) -> None:
    assert (await cliente.post("/api/dispositivos", json=ROBOT, headers=auth(admin))).status_code == 201
    repetido = await cliente.post("/api/dispositivos", json={**ROBOT, "numero_serie": "R-010"}, headers=auth(admin))
    assert repetido.status_code == 409
    assert repetido.json()["error"]["codigo"] == "DUPLICADO"


@pytest.mark.parametrize(
    ("datos", "mensaje"),
    [
        ({**ROBOT, "capacidad_carga_kg": None}, "Un robot requiere la capacidad de carga"),
        ({**ROBOT, "autonomia_vuelo_min": 20}, "La autonomía de vuelo no aplica a los robots"),
        ({**DRONE, "autonomia_vuelo_min": None}, "Un drone requiere la autonomía de vuelo"),
        ({**DRONE, "capacidad_carga_kg": 2}, "La capacidad de carga no aplica a los drones"),
        ({**ROBOT, "estado": "EN_SERVICIO"}, "lo maneja el sistema"),
        ({**ROBOT, "estado": "EN_MANTENIMIENTO"}, "lo maneja el sistema"),
        ({**ROBOT, "capacidad_carga_kg": 0}, "Debe ser mayor que 0"),
        ({**ROBOT, "sensores": ["GPS", "gps"]}, "Hay sensores repetidos"),
        ({**ROBOT, "sensores": []}, "al menos 1"),
        ({**ROBOT, "modelo": ""}, "al menos 1 caracteres"),
        ({k: v for k, v in ROBOT.items() if k != "numero_serie"}, "Campo obligatorio"),
        ({**ROBOT, "tipo": "SUBMARINO"}, "Valor no válido"),
    ],
)
async def test_rf01_valida_campos_obligatorios_y_de_su_tipo(
    cliente: httpx.AsyncClient, admin: Usuario, auth, datos: dict, mensaje: str
) -> None:
    respuesta = await cliente.post("/api/dispositivos", json=datos, headers=auth(admin))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert mensaje in str(respuesta.json()["error"])
