"""Consulta del historial de auditoría (RNF09). Solo administrador."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.auditoria.servicio import consultar_auditoria
from app.nucleo.dependencias import Administrador, Paginacion, Sesion
from app.nucleo.enums import AccionAuditoria
from app.nucleo.esquemas import Esquema, FechaHora, Pagina
from app.usuarios.esquemas import UsuarioResumen

router = APIRouter(prefix="/api/auditoria", tags=["Auditoría"])


class RegistroAuditoriaSalida(Esquema):
    id_auditoria: int
    fecha_hora: FechaHora
    accion: AccionAuditoria
    entidad: str
    id_entidad: int
    usuario: UsuarioResumen


@router.get(
    "",
    response_model=Pagina[RegistroAuditoriaSalida],
    summary="Consultar auditoría (RNF09)",
    description="RNF09. Historial de creaciones, ediciones y bajas hechas por usuarios, con fecha, hora y "
    "responsable. Filtros por usuario, entidad (nombre de la tabla), acción y rango de fechas.",
)
async def listar_auditoria(
    _: Administrador,
    sesion: Sesion,
    paginacion: Paginacion,
    id_usuario: int | None = None,
    entidad: str | None = None,
    accion: AccionAuditoria | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> Pagina[RegistroAuditoriaSalida]:
    pagina = await consultar_auditoria(
        sesion, paginacion, id_usuario=id_usuario, entidad=entidad, accion=accion, desde=desde, hasta=hasta
    )
    return Pagina[RegistroAuditoriaSalida](
        items=[RegistroAuditoriaSalida.model_validate(r) for r in pagina.items],
        total=pagina.total,
        limite=pagina.limite,
        desplazamiento=pagina.desplazamiento,
    )
