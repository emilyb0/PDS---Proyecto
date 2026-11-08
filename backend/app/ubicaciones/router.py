"""Ruta del catálogo de ubicaciones (RF05). Ambos roles. La zona de operación será del módulo RF25 (pendiente)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.nucleo.dependencias import ContenedorDep, Sesion, UsuarioActual
from app.ubicaciones.servicio import listar_ubicaciones

router = APIRouter(tags=["Ubicaciones"])


class UbicacionSalida(BaseModel):
    id_ubicacion: int
    nombre: str
    latitud: float
    longitud: float
    es_base: bool


@router.get(
    "/api/ubicaciones",
    response_model=list[UbicacionSalida],
    summary="Catálogo de ubicaciones (RF05)",
    description="RF05. Puntos del campus para el origen y el destino de las reservas. `es_base` marca la base de "
    "operaciones, desde donde salen y adonde vuelven los dispositivos. Coordenadas de ejemplo.",
)
async def ubicaciones(_: UsuarioActual, sesion: Sesion, contenedor: ContenedorDep) -> list[UbicacionSalida]:
    base = contenedor.config.base_ubicacion
    return [
        UbicacionSalida(
            id_ubicacion=u.id_ubicacion,
            nombre=u.nombre,
            latitud=float(u.latitud),
            longitud=float(u.longitud),
            es_base=u.nombre == base,
        )
        for u in await listar_ubicaciones(sesion)
    ]
