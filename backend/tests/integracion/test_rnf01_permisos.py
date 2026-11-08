"""RNF01 — Solo el administrador crea usuarios, cambia permisos, registra dispositivos y consulta la auditoría.

Aquí van los endpoints de administrador del núcleo (entrega 1). Cada módulo removible prueba los suyos en
``tests/modulos/``.
"""

from __future__ import annotations

import httpx
import pytest

from app.usuarios.modelos import Usuario

ENDPOINTS_SOLO_ADMINISTRADOR = [
    (
        "POST",
        "/api/usuarios",
        {
            "nombre": "X",
            "correo_institucional": "x@campus.edu.co",
            "contrasena": "Segura123*",
            "rol": "OPERADOR",
        },
    ),
    ("GET", "/api/usuarios", None),
    ("PATCH", "/api/usuarios/1", {"rol": "OPERADOR"}),
    ("POST", "/api/dispositivos", {"tipo": "ROBOT", "numero_serie": "R-9", "modelo": "X", "capacidad_carga_kg": 1}),
    ("GET", "/api/auditoria", None),
    (
        "POST",
        "/api/reservas",
        {
            "tipo_servicio": "PEDIDO_CAFETERIA",
            "fecha": "2026-12-01",
            "hora_inicio": "10:00",
            "duracion_estimada_min": 30,
            "id_origen": 1,
            "id_destino": 2,
            "id_dispositivo": 1,
            "id_operador": 1,
        },
    ),
]


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), ENDPOINTS_SOLO_ADMINISTRADOR)
async def test_rnf01_operador_recibe_403_en_endpoints_de_administrador(
    cliente: httpx.AsyncClient,
    admin: Usuario,
    operador: Usuario,
    auth,
    metodo: str,
    ruta: str,
    cuerpo: dict | None,
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo, headers=auth(operador))
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "SIN_PERMISO"


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), ENDPOINTS_SOLO_ADMINISTRADOR)
async def test_rnf01_sin_token_responde_401(
    cliente: httpx.AsyncClient, metodo: str, ruta: str, cuerpo: dict | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


async def test_rnf01_administrador_cambia_rol_y_aplica_de_inmediato(
    cliente: httpx.AsyncClient, admin: Usuario, operador: Usuario, auth
) -> None:
    cabecera_operador = auth(operador)
    assert (await cliente.get("/api/usuarios", headers=cabecera_operador)).status_code == 403

    respuesta = await cliente.patch(
        f"/api/usuarios/{operador.id_usuario}",
        json={"rol": "ADMINISTRADOR", "nombre": "Óscar Admin"},
        headers=auth(admin),
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "ADMINISTRADOR"
    assert respuesta.json()["nombre"] == "Óscar Admin"

    # El rol se lee de la base en cada petición: el mismo token ya tiene permisos de administrador.
    assert (await cliente.get("/api/usuarios", headers=cabecera_operador)).status_code == 200


async def test_rnf01_editar_sin_campos_o_con_campos_extra_da_422(
    cliente: httpx.AsyncClient, admin: Usuario, operador: Usuario, auth
) -> None:
    ruta = f"/api/usuarios/{operador.id_usuario}"
    vacio = await cliente.patch(ruta, json={}, headers=auth(admin))
    assert vacio.status_code == 422
    assert vacio.json()["error"]["mensaje"] == "Indique el nombre o el rol a cambiar."
    extra = await cliente.patch(ruta, json={"correo_institucional": "otro@campus.edu.co"}, headers=auth(admin))
    assert extra.status_code == 422
