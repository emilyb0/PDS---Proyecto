"""RF18 — Registrar usuario."""

from __future__ import annotations

import httpx

from app.usuarios.modelos import Usuario

NUEVO = {
    "nombre": "Lucía Operadora",
    "correo_institucional": "Lucia@Campus.edu.co",
    "contrasena": "Segura123*",
    "rol": "OPERADOR",
}


async def test_rf18_registra_usuario_activo_sin_devolver_contrasena(
    cliente: httpx.AsyncClient, admin: Usuario, auth
) -> None:
    respuesta = await cliente.post("/api/usuarios", json=NUEVO, headers=auth(admin))
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ACTIVO"
    assert cuerpo["rol"] == "OPERADOR"
    assert cuerpo["correo_institucional"] == "lucia@campus.edu.co"
    assert cuerpo["fecha_creacion"] == "2026-11-09T08:00:00-05:00"
    assert "contrasena" not in cuerpo and "contrasena_hash" not in cuerpo

    # El nuevo usuario puede iniciar sesión.
    login = await cliente.post("/api/auth/login", json={"correo": "lucia@campus.edu.co", "contrasena": "Segura123*"})
    assert login.status_code == 200


async def test_rf18_correo_repetido_sin_importar_mayusculas_da_409(
    cliente: httpx.AsyncClient, admin: Usuario, auth
) -> None:
    assert (await cliente.post("/api/usuarios", json=NUEVO, headers=auth(admin))).status_code == 201
    repetido = {**NUEVO, "correo_institucional": "LUCIA@campus.edu.co", "nombre": "Otra"}
    respuesta = await cliente.post("/api/usuarios", json=repetido, headers=auth(admin))
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DUPLICADO"


async def test_rf18_valida_campos_obligatorios_dominio_y_contrasena(
    cliente: httpx.AsyncClient, admin: Usuario, auth
) -> None:
    corta = await cliente.post("/api/usuarios", json={**NUEVO, "contrasena": "corta"}, headers=auth(admin))
    assert corta.status_code == 422
    assert corta.json()["error"]["detalles"]["campos"][0] == {
        "campo": "contrasena",
        "mensaje": "Debe tener al menos 8 caracteres.",
    }

    otro_dominio = await cliente.post(
        "/api/usuarios", json={**NUEVO, "correo_institucional": "x@gmail.com"}, headers=auth(admin)
    )
    assert otro_dominio.status_code == 422
    assert "@campus.edu.co" in otro_dominio.json()["error"]["mensaje"]

    rol_invalido = await cliente.post("/api/usuarios", json={**NUEVO, "rol": "SUPERUSUARIO"}, headers=auth(admin))
    assert rol_invalido.status_code == 422

    sin_nombre = {k: v for k, v in NUEVO.items() if k != "nombre"}
    assert (await cliente.post("/api/usuarios", json=sin_nombre, headers=auth(admin))).status_code == 422


async def test_rf18_lista_usuarios_con_filtros(
    cliente: httpx.AsyncClient, admin: Usuario, operador: Usuario, auth
) -> None:
    respuesta = await cliente.get("/api/usuarios", params={"rol": "OPERADOR", "estado": "ACTIVO"}, headers=auth(admin))
    assert respuesta.status_code == 200
    pagina = respuesta.json()
    assert pagina["total"] == 1
    assert pagina["limite"] == 50 and pagina["desplazamiento"] == 0
    assert pagina["items"][0]["id_usuario"] == operador.id_usuario
