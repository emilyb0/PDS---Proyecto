"""Esquemas de alertas (RF11, RF16, RF25) y atención (RF27)."""

from __future__ import annotations

from pydantic import BaseModel

from app.nucleo.enums import CausaAlerta, TipoAlerta
from app.nucleo.esquemas import FechaHora
from app.usuarios.esquemas import UsuarioResumen


class AtencionSalida(BaseModel):
    id_atencion: int
    id_alerta: int
    operador: UsuarioResumen
    fecha_hora: FechaHora
    causa_revisada: str
    observaciones: str | None


class AlertaSalida(BaseModel):
    """Misma forma para alertas de servicio y de mantenimiento; los campos que no aplican van en ``null``."""

    id_alerta: int
    tipo: TipoAlerta
    causa: CausaAlerta | None
    descripcion: str
    fecha_hora: FechaHora
    id_dispositivo: int
    numero_serie: str
    id_bitacora: int | None
    id_incidencia: int | None
    id_operador: int | None
    latitud: float | None
    longitud: float | None
    atendida: bool | None
    atencion: AtencionSalida | None
    dias_desde_ultimo: int | None
    horas_desde_ultimo: float | None
