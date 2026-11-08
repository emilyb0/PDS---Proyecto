"""Fábrica de la aplicación FastAPI.

Producción y Docker: ``uvicorn app.main:crear_app --factory --workers 1``.
Pruebas: ``crear_app(contenedor)`` con adaptadores falsos y reloj simulado.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import VERSION
from app.alertas.router import router as router_alertas
from app.auditoria.router import router as router_auditoria
from app.config import Configuracion
from app.contenedor import Contenedor
from app.demo.router import router as router_demo
from app.dispositivos.router import router as router_dispositivos
from app.modulos import seleccionar_modulos
from app.nucleo.errores import registrar_manejadores
from app.nucleo.registro import configurar_registro
from app.reservas.router import router as router_reservas
from app.salud import router as router_salud
from app.servicios.router import router_bitacoras, router_monitoreo
from app.tareas.planificador import Planificador
from app.ubicaciones.router import router as router_ubicaciones
from app.usuarios.router import router_sesion, router_usuarios

DESCRIPCION = """
API del **sistema centralizado de robots y drones** (prototipo, Procesos y Diseño de Software).

- Autenticación: `POST /api/auth/login` y luego el botón **Authorize** con el token.
- Fechas en hora de Colombia (ISO 8601 con `-05:00`); errores con el formato
  `{"error": {"codigo", "mensaje", "detalles"}}`.
- Cada endpoint indica en su descripción el requisito (RF/RNF) que cumple.
- Guía para el frontend: `docs/guia-frontend.md`.
"""

ETIQUETAS = [
    {"name": "Sesión", "description": "Inicio de sesión y funciones del rol (RF20)."},
    {"name": "Usuarios", "description": "Registro y edición de usuarios (RF18, RNF01)."},
    {"name": "Dispositivos", "description": "Inventario: registrar y consultar (RF01, RF04)."},
    {"name": "Ubicaciones", "description": "Catálogo de origen y destino (RF05)."},
    {"name": "Reservas", "description": "Crear y consultar reservas, con cruce, batería y sensores (RF05–RF07)."},
    {"name": "Bitácoras", "description": "Bitácora de cada servicio: salida, regreso, ruta e incidencias (RF08)."},
    {"name": "Monitoreo", "description": "Panel de monitoreo y tiempo real por SSE (RF09, RF10, RNF02)."},
    {"name": "Alertas", "description": "Alertas de servicio y de mantenimiento preventivo (RF11)."},
    {"name": "Auditoría", "description": "Historial de creaciones, ediciones y bajas (RNF09)."},
    {"name": "Salud", "description": "Estado del servicio (RNF06)."},
    {"name": "Demo", "description": "Controles para la presentación (solo con MODO_DEMO=true)."},
]


def crear_app(contenedor: Contenedor | None = None) -> FastAPI:
    """Crea la aplicación. Sin ``contenedor``, lo arma desde las variables de entorno al arrancar."""
    config = contenedor.config if contenedor is not None else Configuracion()
    # Los routers se incluyen al crear la app; por eso los módulos activos se eligen aquí y no en el arranque.
    modulos = contenedor.modulos if contenedor is not None else seleccionar_modulos(config.modulos_activos)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        propio = contenedor is None
        if propio:
            configurar_registro(config.nivel_log)
            app.state.contenedor = Contenedor.crear(config, modulos=modulos)
        # Inicio de reservas, monitoreo, tareas diarias y eventos del dispositivo (un solo proceso).
        planificador = Planificador(app.state.contenedor)
        app.state.planificador = planificador
        if app.state.contenedor.config.tareas_activas:
            await planificador.iniciar()
        try:
            yield
        finally:
            await planificador.detener()
            if propio:
                await app.state.contenedor.cerrar()

    app = FastAPI(
        title="Sistema centralizado de robots y drones",
        version=VERSION,
        description=DESCRIPCION,
        # Sin repetir: varios módulos pueden declarar la misma etiqueta (por ejemplo, "Demo").
        openapi_tags=list(
            {e["name"]: e for e in ETIQUETAS + [e for m in modulos for e in m.etiquetas_openapi]}.values()
        ),
        lifespan=ciclo_de_vida,
    )
    if contenedor is not None:
        app.state.contenedor = contenedor

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.lista_cors_origenes,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
    )
    registrar_manejadores(app)

    app.include_router(router_salud)
    app.include_router(router_sesion)
    app.include_router(router_usuarios)
    app.include_router(router_dispositivos)
    app.include_router(router_ubicaciones)
    app.include_router(router_reservas)
    app.include_router(router_bitacoras)
    app.include_router(router_monitoreo)
    app.include_router(router_alertas)
    app.include_router(router_auditoria)
    app.include_router(router_demo)
    # Módulos removibles de la entrega 2 (CLAUDE.md): cada uno trae sus propios routers.
    for modulo in modulos:
        for router in modulo.routers:
            app.include_router(router)
    return app
