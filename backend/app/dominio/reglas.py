"""Reglas de negocio puras (sin base de datos)."""

from __future__ import annotations

from app.nucleo.enums import TipoDispositivo, TipoServicio

# Del enunciado: los robots transportan y los drones graban (especificación 7.2, supuesto 1).
TIPO_REQUERIDO: dict[TipoServicio, TipoDispositivo] = {
    TipoServicio.ENTREGA_DOCUMENTOS: TipoDispositivo.ROBOT,
    TipoServicio.PEDIDO_CAFETERIA: TipoDispositivo.ROBOT,
    TipoServicio.GRABACION_EVENTO: TipoDispositivo.DRONE,
}

NOMBRE_SERVICIO = {
    TipoServicio.ENTREGA_DOCUMENTOS: "entrega de documentos",
    TipoServicio.PEDIDO_CAFETERIA: "pedido de cafetería",
    TipoServicio.GRABACION_EVENTO: "grabación de evento",
}


def tipo_requerido(tipo_servicio: TipoServicio) -> TipoDispositivo:
    return TIPO_REQUERIDO[tipo_servicio]
