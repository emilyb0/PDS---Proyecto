"""Esquemas de bitácoras (RF08) y monitoreo (RF09)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from app.alertas.esquemas import AlertaSalida
from app.dispositivos.esquemas import DispositivoResumen
from app.nucleo.enums import (
    EstadoDispositivo,
    EstadoSensor,
    EstadoServicio,
    TipoDispositivo,
    TipoIncidencia,
    TipoServicio,
)
from app.nucleo.esquemas import FechaHora
from app.reservas.esquemas import ReservaSalida, UbicacionResumen
from app.usuarios.esquemas import UsuarioResumen


class BitacoraSalida(BaseModel):
    id_bitacora: int
    id_reserva: int
    estado: EstadoServicio
    tipo_servicio: TipoServicio
    hora_salida: FechaHora
    hora_regreso: FechaHora | None
    hora_entrega: FechaHora | None
    entregado: bool
    dispositivo: DispositivoResumen
    operador: UsuarioResumen
    numero_incidencias: int
    tiene_video: bool


class IncidenciaSalida(BaseModel):
    id_incidencia: int
    fecha_hora: FechaHora
    tipo: TipoIncidencia
    descripcion: str
    latitud: float | None
    longitud: float | None
    id_alerta: int | None


class VideoResumen(BaseModel):
    id_video: int
    fecha_grabacion: FechaHora
    duracion_seg: int
    eliminado: bool
    fecha_eliminacion: date | None


class BitacoraDetalle(BitacoraSalida):
    reserva: ReservaSalida
    horas_uso: float | None
    incidencias: list[IncidenciaSalida]
    video: VideoResumen | None


class LecturaSensorSalida(BaseModel):
    id_sensor: int
    nombre: str
    estado: EstadoSensor


class PuntoRuta(BaseModel):
    fecha_hora: FechaHora
    latitud: float
    longitud: float
    nivel_bateria: int
    estado_servicio: str
    sensores: list[LecturaSensorSalida]


class RutaSalida(BaseModel):
    id_bitacora: int
    puntos: list[PuntoRuta]


class ServicioMonitoreo(BaseModel):
    id_bitacora: int
    id_reserva: int
    tipo_servicio: TipoServicio
    estado: EstadoServicio
    hora_salida: FechaHora
    fin_estimado: FechaHora
    destino: UbicacionResumen
    operador: UsuarioResumen


class DispositivoMonitoreo(BaseModel):
    id_dispositivo: int
    numero_serie: str
    tipo: TipoDispositivo
    modelo: str
    estado: EstadoDispositivo
    telemetria: dict[str, Any] | None
    servicio: ServicioMonitoreo | None


class MonitoreoSalida(BaseModel):
    generado: FechaHora
    intervalo_seg: float
    dispositivos: list[DispositivoMonitoreo]
    alertas_abiertas: list[AlertaSalida]
