"""Rutas de bitácoras (RF08) y monitoreo (RF09, RF10, RNF02). Ambos roles."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query
from sse_starlette.event import ServerSentEvent
from sse_starlette.sse import EventSourceResponse

from app.contenedor import Contenedor
from app.nucleo.dependencias import ContenedorDep, Paginacion, Sesion, UsuarioActual, autenticar_token
from app.nucleo.enums import EstadoServicio
from app.nucleo.errores import ErrorAplicacion, ErrorNoAutenticado
from app.nucleo.esquemas import Pagina
from app.servicios.consultas import foto_monitoreo, listar_bitacoras, obtener_bitacora, obtener_ruta
from app.servicios.esquemas import BitacoraDetalle, BitacoraSalida, MonitoreoSalida, RutaSalida

registro = logging.getLogger(__name__)

router_bitacoras = APIRouter(prefix="/api/bitacoras", tags=["Bitácoras"])
router_monitoreo = APIRouter(prefix="/api/monitoreo", tags=["Monitoreo"])


# ============================================================================ bitácoras (RF08)


@router_bitacoras.get(
    "",
    response_model=Pagina[BitacoraSalida],
    summary="Listar bitácoras de servicio (RF08)",
    description="RF08, RNF03. Bitácoras de la más reciente a la más antigua, con dispositivo, operador, número de "
    "incidencias y si ya tiene video. Filtros `desde` y `hasta` (fecha de salida), `id_dispositivo` y `estado`.",
)
async def listar(
    _: UsuarioActual,
    sesion: Sesion,
    paginacion: Paginacion,
    desde: date | None = None,
    hasta: date | None = None,
    id_dispositivo: int | None = None,
    estado: EstadoServicio | None = None,
) -> Pagina[BitacoraSalida]:
    return await listar_bitacoras(
        sesion, paginacion, desde=desde, hasta=hasta, id_dispositivo=id_dispositivo, estado=estado
    )


@router_bitacoras.get(
    "/{id_bitacora:int}",
    response_model=BitacoraDetalle,
    summary="Detalle de bitácora (RF08)",
    description="RF08, RF12. Hora de salida, de entrega y de regreso, reserva (el código de entrega solo lo ve el "
    "administrador), dispositivo, operador responsable, incidencias (con la alerta que generaron) y video.",
)
async def detalle(id_bitacora: int, usuario: UsuarioActual, sesion: Sesion) -> BitacoraDetalle:
    return await obtener_bitacora(sesion, id_bitacora, ver_codigo=usuario.es_administrador)


@router_bitacoras.get(
    "/{id_bitacora:int}/ruta",
    response_model=RutaSalida,
    summary="Ruta recorrida (RF08)",
    description="RF08, RF09. Puntos de la ruta en orden, con batería, fase reportada y estado de cada sensor.",
)
async def ruta(id_bitacora: int, _: UsuarioActual, sesion: Sesion) -> RutaSalida:
    return await obtener_ruta(sesion, id_bitacora)


# ============================================================================ monitoreo (RF09, RF10)


@router_monitoreo.get(
    "",
    response_model=MonitoreoSalida,
    summary="Foto del monitoreo (RF09)",
    description="RF09. Todos los dispositivos que no están dados de baja, con su última telemetría (la misma forma "
    "del evento SSE `telemetria`), su servicio activo y las alertas abiertas. Después se actualiza con "
    "`GET /api/monitoreo/stream`.",
)
async def monitoreo(_: UsuarioActual, sesion: Sesion, contenedor: ContenedorDep) -> MonitoreoSalida:
    return await foto_monitoreo(sesion, contenedor)


async def _sigue_valido(contenedor: Contenedor, token: str) -> bool:
    """RF19: el usuario sigue activo y el token no venció."""
    try:
        async with contenedor.sesiones() as sesion:
            await autenticar_token(token, contenedor, sesion)
        return True
    except ErrorAplicacion:
        return False


def _ping() -> ServerSentEvent:
    return ServerSentEvent(comment="ping")


@router_monitoreo.get(
    "/stream",
    summary="Monitoreo en tiempo real por SSE (RF10, RNF02)",
    description="RF10, RNF02. Server-Sent Events. El token va en `?token=` porque `EventSource` no envía cabeceras "
    "(no se escribe en los logs). Eventos: `telemetria` (cada ≤ 5 s por dispositivo), `alerta`, `servicio`, "
    "`servicio_en_espera` y `servicio_no_iniciado`; los RF pendientes agregarán `alerta_atendida`, `entrega` y "
    "`orden`. Cada 15 s llega un comentario `: ping`. Con `Last-Event-ID` reenvía los eventos que faltaron "
    "(guarda los últimos 200). Si el usuario es desactivado o el token vence, el flujo se cierra (se revisa cada "
    "30 s).",
    response_class=EventSourceResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Flujo de eventos"}},
)
async def flujo(
    contenedor: ContenedorDep,
    token: Annotated[str | None, Query(description="Token JWT de la sesión")] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> EventSourceResponse:
    if not token:
        raise ErrorNoAutenticado("Falta el token de acceso (parámetro token).")
    async with contenedor.sesiones() as sesion:
        await autenticar_token(token, contenedor, sesion)  # 401 antes de abrir el flujo
    ultimo = int(last_event_id) if last_event_id and last_event_id.strip().isdigit() else None
    revalidar = contenedor.config.sse_revalidar_seg

    async def eventos() -> AsyncIterator[dict[str, Any]]:
        with contenedor.bus.suscribir(ultimo) as suscripcion:
            proxima_revision = time.monotonic() + revalidar
            while not suscripcion.desbordada:
                evento = await suscripcion.siguiente(max(0.0, proxima_revision - time.monotonic()))
                if evento is not None:
                    yield {
                        "event": evento.tipo,
                        "id": str(evento.id),
                        "data": json.dumps(evento.datos, ensure_ascii=False),
                    }
                if time.monotonic() >= proxima_revision:
                    if not await _sigue_valido(contenedor, token):
                        registro.info("Se cerró un flujo SSE: el usuario ya no está activo o el token venció.")
                        return
                    proxima_revision = time.monotonic() + revalidar

    return EventSourceResponse(eventos(), ping=contenedor.config.sse_ping_seg, ping_message_factory=_ping)
