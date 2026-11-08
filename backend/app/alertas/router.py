"""Rutas de alertas (RF11). Ambos roles. RF16 y RF25 (pendientes) agregarán sus tipos de alerta."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.alertas.esquemas import AlertaSalida
from app.alertas.servicio import consultar_alertas, obtener_alerta
from app.nucleo.dependencias import Paginacion, Sesion, UsuarioActual
from app.nucleo.enums import TipoAlerta
from app.nucleo.esquemas import Pagina

router = APIRouter(prefix="/api/alertas", tags=["Alertas"])


@router.get(
    "",
    response_model=Pagina[AlertaSalida],
    summary="Consultar alertas (RF11)",
    description="RF11. Alertas de servicio (batería, sensor, retraso), de la más reciente a la más antigua. "
    "Filtros `tipo`, `atendida` (solo aplica a las de servicio), `id_dispositivo`, `desde` y `hasta`. Los RF "
    "pendientes agregarán las de salida de zona (RF25) y de mantenimiento preventivo (RF16).",
)
async def listar_alertas(
    _: UsuarioActual,
    sesion: Sesion,
    paginacion: Paginacion,
    tipo: TipoAlerta | None = None,
    atendida: bool | None = None,
    id_dispositivo: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> Pagina[AlertaSalida]:
    return await consultar_alertas(
        sesion, paginacion, tipo=tipo, atendida=atendida, id_dispositivo=id_dispositivo, desde=desde, hasta=hasta
    )


@router.get(
    "/{id_alerta}",
    response_model=AlertaSalida,
    summary="Detalle de alerta (RF11)",
    description="RF11. Una alerta. La atención (RF27, pendiente) vendrá en `atencion`.",
)
async def detalle_alerta(id_alerta: int, _: UsuarioActual, sesion: Sesion) -> AlertaSalida:
    return await obtener_alerta(sesion, id_alerta)
