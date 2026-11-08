"""Esquemas de reservas del núcleo (RF05–RF07)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.dispositivos.esquemas import DispositivoResumen
from app.nucleo.enums import EstadoReserva, TipoServicio
from app.nucleo.esquemas import Advertencia, EsquemaEntrada, FechaHora, Hora
from app.reservas.modelos import Reserva
from app.usuarios.esquemas import UsuarioResumen


class DatosHorario(EsquemaEntrada):
    """Datos de la solicitud que comparten crear (RF05) y sugerir (RF22)."""

    tipo_servicio: TipoServicio
    fecha: date
    hora_inicio: Hora = Field(examples=["10:00"])
    duracion_estimada_min: int = Field(ge=1, le=480)
    id_origen: int
    id_destino: int


class ReservaCrear(DatosHorario):
    id_dispositivo: int
    id_operador: int


class UbicacionResumen(BaseModel):
    id_ubicacion: int
    nombre: str


class ReservaSalida(BaseModel):
    id_reserva: int
    tipo_servicio: TipoServicio
    estado: EstadoReserva
    fecha: date
    hora_inicio: Hora
    hora_fin: Hora
    duracion_estimada_min: int
    inicio: FechaHora
    fin: FechaHora
    origen: UbicacionResumen
    destino: UbicacionResumen
    dispositivo: DispositivoResumen
    operador: UsuarioResumen
    administrador: UsuarioResumen
    codigo_entrega: str | None = Field(description="Solo para el administrador y en robots (RF24)")
    motivo_cambio: str | None
    fecha_creacion: FechaHora
    id_bitacora: int | None
    advertencias: list[Advertencia] = Field(default_factory=list)

    @classmethod
    def de(cls, r: Reserva, *, ver_codigo: bool, advertencias: list[Advertencia] | None = None) -> ReservaSalida:
        """Necesita cargadas las relaciones ``origen``, ``destino``, ``dispositivo``, ``operador``,
        ``administrador`` y ``bitacora`` (ver ``opciones_reserva``)."""
        return cls(
            id_reserva=r.id_reserva,
            tipo_servicio=r.tipo_servicio,
            estado=r.estado,
            fecha=r.fecha,
            hora_inicio=r.hora_inicio,
            hora_fin=r.hora_fin(),
            duracion_estimada_min=r.duracion_estimada_min,
            inicio=r.inicio,
            fin=r.fin,
            origen=UbicacionResumen(id_ubicacion=r.origen.id_ubicacion, nombre=r.origen.nombre),
            destino=UbicacionResumen(id_ubicacion=r.destino.id_ubicacion, nombre=r.destino.nombre),
            dispositivo=DispositivoResumen.de(r.dispositivo),
            operador=UsuarioResumen.model_validate(r.operador),
            administrador=UsuarioResumen.model_validate(r.administrador),
            codigo_entrega=r.codigo_entrega if ver_codigo else None,
            motivo_cambio=r.motivo_cambio,
            fecha_creacion=r.fecha_creacion,
            id_bitacora=r.bitacora.id_bitacora if r.bitacora is not None else None,
            advertencias=advertencias or [],
        )
