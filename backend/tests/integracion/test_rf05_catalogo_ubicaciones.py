"""RF05 — Catálogo de ubicaciones para el origen y el destino de las reservas."""

from __future__ import annotations

import httpx

from app.contenedor import Contenedor
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_ubicaciones


async def test_rf05_catalogo_de_ubicaciones_marca_la_base(
    cliente: httpx.AsyncClient, contenedor: Contenedor, operador: Usuario, auth
) -> None:
    await crear_ubicaciones(contenedor)
    respuesta = await cliente.get("/api/ubicaciones", headers=auth(operador))
    assert respuesta.status_code == 200
    ubicaciones = respuesta.json()
    assert [u["nombre"] for u in ubicaciones] == ["Base de operaciones", "Cafetería", "Coliseo", "Rectoría"]
    assert [u["nombre"] for u in ubicaciones if u["es_base"]] == ["Base de operaciones"]
    assert ubicaciones[0]["latitud"] == 4.638 and ubicaciones[0]["longitud"] == -74.084
    assert (await cliente.get("/api/ubicaciones")).status_code == 401
