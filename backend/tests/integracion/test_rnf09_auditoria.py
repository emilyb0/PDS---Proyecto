"""RNF09 — Cada creación, edición o baja del núcleo queda en la auditoría, en la misma transacción.

Las acciones de los módulos removibles (desactivar usuario, editar o dar de baja dispositivo, mantenimiento…)
se prueban en ``tests/modulos/`` junto con su módulo.
"""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auditoria.modelos import RegistroAuditoria
from app.nucleo.reloj import RelojSimulado
from app.usuarios.modelos import Usuario

NUEVO_USUARIO = {
    "nombre": "Nuevo",
    "correo_institucional": "nuevo@campus.edu.co",
    "contrasena": "Segura123*",
    "rol": "OPERADOR",
}


async def filas_auditoria(sesion: AsyncSession) -> list[tuple[str, str, int, int]]:
    filas = await sesion.execute(
        select(
            RegistroAuditoria.accion,
            RegistroAuditoria.entidad,
            RegistroAuditoria.id_entidad,
            RegistroAuditoria.id_usuario,
        ).order_by(RegistroAuditoria.id_auditoria)
    )
    return [(a.value, e, i, u) for a, e, i, u in filas]


async def test_rnf09_crear_y_editar_usuario_quedan_auditados(
    cliente: httpx.AsyncClient, sesion: AsyncSession, admin: Usuario, reloj: RelojSimulado, auth
) -> None:
    creado = await cliente.post("/api/usuarios", headers=auth(admin), json=NUEVO_USUARIO)
    id_nuevo = creado.json()["id_usuario"]
    reloj.avanzar(minutes=5)
    await cliente.patch(f"/api/usuarios/{id_nuevo}", json={"nombre": "Nuevo Nombre"}, headers=auth(admin))

    assert await filas_auditoria(sesion) == [
        ("CREAR", "usuario", id_nuevo, admin.id_usuario),
        ("EDITAR", "usuario", id_nuevo, admin.id_usuario),
    ]

    consulta = await cliente.get(
        "/api/auditoria", params={"entidad": "usuario", "accion": "EDITAR"}, headers=auth(admin)
    )
    assert consulta.status_code == 200
    [fila] = consulta.json()["items"]
    assert fila["fecha_hora"] == "2026-11-09T08:05:00-05:00"
    assert fila["usuario"] == {"id_usuario": admin.id_usuario, "nombre": "Ana Admin"}


async def test_rnf09_registrar_dispositivo_queda_auditado(
    cliente: httpx.AsyncClient, sesion: AsyncSession, admin: Usuario, auth
) -> None:
    creado = await cliente.post(
        "/api/dispositivos",
        headers=auth(admin),
        json={"tipo": "DRONE", "numero_serie": "D-100", "modelo": "Halcón", "autonomia_vuelo_min": 30},
    )
    assert await filas_auditoria(sesion) == [
        ("CREAR", "dispositivo", creado.json()["id_dispositivo"], admin.id_usuario)
    ]


async def test_rnf09_operacion_fallida_no_deja_auditoria(
    cliente: httpx.AsyncClient, sesion: AsyncSession, admin: Usuario, operador: Usuario, auth
) -> None:
    repetido = await cliente.post(
        "/api/usuarios", headers=auth(admin), json={**NUEVO_USUARIO, "correo_institucional": "operador1@campus.edu.co"}
    )
    assert repetido.status_code == 409
    ultimo_admin = await cliente.patch(
        f"/api/usuarios/{admin.id_usuario}", json={"rol": "OPERADOR"}, headers=auth(admin)
    )
    assert ultimo_admin.status_code == 409
    assert await filas_auditoria(sesion) == []


async def test_rnf09_filtros_de_la_consulta(
    cliente: httpx.AsyncClient, admin: Usuario, operador: Usuario, reloj: RelojSimulado, auth
) -> None:
    await cliente.patch(f"/api/usuarios/{operador.id_usuario}", json={"nombre": "A"}, headers=auth(admin))
    reloj.avanzar(days=2)
    await cliente.patch(f"/api/usuarios/{operador.id_usuario}", json={"nombre": "B"}, headers=auth(admin))

    def consultar(**params: object):
        return cliente.get("/api/auditoria", params=params, headers=auth(admin))

    assert (await consultar(desde="2026-11-09", hasta="2026-11-09")).json()["total"] == 1
    assert (await consultar(desde="2026-11-10")).json()["total"] == 1
    assert (await consultar(id_usuario=admin.id_usuario)).json()["total"] == 2
    assert (await consultar(id_usuario=operador.id_usuario)).json()["total"] == 0
    rango_invertido = await consultar(desde="2026-11-11", hasta="2026-11-09")
    assert rango_invertido.status_code == 422
