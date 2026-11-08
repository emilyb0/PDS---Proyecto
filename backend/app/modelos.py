"""Importa todos los modelos para que SQLAlchemy resuelva las relaciones entre módulos."""

from app.alertas.modelos import Alerta, AlertaMantenimiento, AlertaServicio, AtencionAlerta
from app.auditoria.modelos import RegistroAuditoria
from app.dispositivos.modelos import Dispositivo, Drone, Robot, Sensor
from app.mantenimiento.modelos import Mantenimiento
from app.reservas.modelos import Reserva
from app.servicios.modelos import BitacoraServicio, Incidencia, LecturaSensor, RegistroTelemetria
from app.ubicaciones.modelos import Ubicacion, VerticeZona, ZonaOperacion
from app.usuarios.modelos import Usuario
from app.videos.modelos import Video

__all__ = [
    "Alerta",
    "AlertaMantenimiento",
    "AlertaServicio",
    "AtencionAlerta",
    "BitacoraServicio",
    "Dispositivo",
    "Drone",
    "Incidencia",
    "LecturaSensor",
    "Mantenimiento",
    "RegistroAuditoria",
    "RegistroTelemetria",
    "Reserva",
    "Robot",
    "Sensor",
    "Ubicacion",
    "Usuario",
    "VerticeZona",
    "Video",
    "ZonaOperacion",
]
