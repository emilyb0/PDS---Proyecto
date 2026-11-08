"""RF20 — Iniciar sesión: usuario activo con datos correctos entra y ve solo las funciones de su rol."""

from __future__ import annotations

import httpx

from app.nucleo.reloj import RelojSimulado
from app.usuarios.modelos import Usuario
from app.usuarios.permisos import FUNCIONES_OPERADOR


async def test_rf20_login_correcto_devuelve_token_usuario_y_funciones(
    cliente: httpx.AsyncClient, admin: Usuario
) -> None:
    respuesta = await cliente.post("/api/auth/login", json={"correo": "ADMIN@campus.edu.co", "contrasena": "Admin123*"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "bearer"
    assert cuerpo["expira"] == "2026-11-09T16:00:00-05:00"  # 8 horas
    assert cuerpo["usuario"]["rol"] == "ADMINISTRADOR"
    assert "usuarios.gestionar" in cuerpo["funciones"]

    yo = await cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {cuerpo['token']}"})
    assert yo.status_code == 200
    assert yo.json()["usuario"]["id_usuario"] == admin.id_usuario


async def test_rf20_operador_solo_recibe_funciones_de_su_rol(cliente: httpx.AsyncClient, operador: Usuario) -> None:
    respuesta = await cliente.post(
        "/api/auth/login", json={"correo": "operador1@campus.edu.co", "contrasena": "Operador123*"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["funciones"] == FUNCIONES_OPERADOR


async def test_rf20_datos_incorrectos_mismo_mensaje(cliente: httpx.AsyncClient, admin: Usuario) -> None:
    errada = await cliente.post("/api/auth/login", json={"correo": "admin@campus.edu.co", "contrasena": "mala"})
    inexistente = await cliente.post("/api/auth/login", json={"correo": "nadie@campus.edu.co", "contrasena": "x"})
    for respuesta in (errada, inexistente):
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == {
            "codigo": "NO_AUTENTICADO",
            "mensaje": "Correo o contraseña incorrectos.",
            "detalles": None,
        }


async def test_rf20_sin_token_token_invalido_o_vencido_da_401(
    cliente: httpx.AsyncClient, admin: Usuario, reloj: RelojSimulado, auth
) -> None:
    assert (await cliente.get("/api/auth/yo")).status_code == 401
    assert (await cliente.get("/api/auth/yo", headers={"Authorization": "Bearer basura"})).status_code == 401
    assert (await cliente.get("/api/auth/yo", headers={"Authorization": "Basic YTpi"})).status_code == 401

    cabecera = auth(admin)
    reloj.avanzar(hours=8)
    vencido = await cliente.get("/api/auth/yo", headers=cabecera)
    assert vencido.status_code == 401
    assert vencido.headers["WWW-Authenticate"] == "Bearer"
