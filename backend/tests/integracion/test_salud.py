"""RNF06 — /health informa el estado de la base de datos, el almacenamiento de videos y el simulador."""

from __future__ import annotations

import httpx

from app.contenedor import Contenedor
from app.integraciones.almacenamiento import ErrorAlmacenamiento
from tests.fabrica import crear_ubicaciones


async def test_rnf06_health_reporta_sus_dependencias(cliente: httpx.AsyncClient, contenedor: Contenedor) -> None:
    await crear_ubicaciones(contenedor)
    respuesta = await cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "estado": "ok",
        "base_datos": "ok",
        "almacenamiento": "ok",
        "simulador": "ok",
        "version": "0.1.0",
    }


async def test_rnf06_sin_ubicacion_base_el_simulador_queda_degradado(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "degradado"
    assert respuesta.json()["simulador"] == "sin_base"


async def test_rnf06_si_falla_el_almacenamiento_responde_503(
    cliente: httpx.AsyncClient, contenedor: Contenedor, monkeypatch
) -> None:
    await crear_ubicaciones(contenedor)

    async def falla() -> None:
        raise ErrorAlmacenamiento("sin acceso")

    monkeypatch.setattr(contenedor.almacenamiento, "revisar", falla)
    respuesta = await cliente.get("/health")
    assert respuesta.status_code == 503
    assert respuesta.json()["almacenamiento"] == "error"


async def test_openapi_documenta_los_endpoints_con_su_requisito(cliente: httpx.AsyncClient) -> None:
    esquema = (await cliente.get("/openapi.json")).json()
    login = esquema["paths"]["/api/auth/login"]["post"]
    assert "RF20" in login["description"]
    assert "HTTPBearer" in esquema["components"]["securitySchemes"]


async def test_cors_permite_el_origen_del_frontend(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.options(
        "/api/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
