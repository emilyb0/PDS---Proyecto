"""Forma de los eventos SSE del núcleo (especificación, sección 10; ``docs/guia-frontend.md``, sección 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.dispositivos.modelos import Dispositivo
from app.integraciones.dispositivo.interfaz import TelemetriaDispositivo
from app.nucleo.enums import EstadoSensor


def datos_telemetria(
    dispositivo: Dispositivo,
    telemetria: TelemetriaDispositivo,
    id_bitacora: int | None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evento ``telemetria``. ``fuera_de_zona`` es ``null`` si el módulo RF25 no está activo."""
    datos: dict[str, Any] = {
        "id_dispositivo": dispositivo.id_dispositivo,
        "numero_serie": dispositivo.numero_serie,
        "tipo": dispositivo.tipo.value,
        "id_bitacora": id_bitacora,
        "fecha_hora": telemetria.fecha_hora,
        "latitud": telemetria.latitud,
        "longitud": telemetria.longitud,
        "nivel_bateria": telemetria.nivel_bateria,
        "sensores": [
            {"nombre": nombre, "estado": EstadoSensor(estado).value} for nombre, estado in telemetria.sensores.items()
        ],
        "estado_servicio": telemetria.estado_servicio.value,
        "estado_dispositivo": dispositivo.estado.value,
        "fuera_de_zona": None,
    }
    datos.update(extras or {})
    return datos


def datos_servicio(
    id_bitacora: int, id_reserva: int, id_dispositivo: int, evento: str, fecha_hora: datetime
) -> dict[str, Any]:
    """Evento ``servicio``: ``INICIADO`` o ``FINALIZADO``."""
    return {
        "id_bitacora": id_bitacora,
        "id_reserva": id_reserva,
        "id_dispositivo": id_dispositivo,
        "evento": evento,
        "fecha_hora": fecha_hora,
    }
