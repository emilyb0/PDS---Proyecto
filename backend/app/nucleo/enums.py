"""Enumeraciones del dominio. Reflejan los tipos ENUM de ``esquema_bd.sql`` (no se crean desde aquí)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class RolUsuario(StrEnum):
    ADMINISTRADOR = "ADMINISTRADOR"
    OPERADOR = "OPERADOR"


class EstadoUsuario(StrEnum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class AccionAuditoria(StrEnum):
    CREAR = "CREAR"
    EDITAR = "EDITAR"
    BAJA = "BAJA"


class TipoDispositivo(StrEnum):
    ROBOT = "ROBOT"
    DRONE = "DRONE"


class EstadoDispositivo(StrEnum):
    DISPONIBLE = "DISPONIBLE"
    EN_SERVICIO = "EN_SERVICIO"
    EN_CARGA = "EN_CARGA"
    EN_MANTENIMIENTO = "EN_MANTENIMIENTO"
    FUERA_DE_SERVICIO = "FUERA_DE_SERVICIO"


class EstadoSensor(StrEnum):
    OK = "OK"
    FALLA = "FALLA"


class TipoMantenimiento(StrEnum):
    PREVENTIVO = "PREVENTIVO"
    CORRECTIVO = "CORRECTIVO"


class TipoServicio(StrEnum):
    ENTREGA_DOCUMENTOS = "ENTREGA_DOCUMENTOS"
    PEDIDO_CAFETERIA = "PEDIDO_CAFETERIA"
    GRABACION_EVENTO = "GRABACION_EVENTO"


class EstadoReserva(StrEnum):
    PROGRAMADA = "PROGRAMADA"
    EN_CURSO = "EN_CURSO"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


class EstadoServicio(StrEnum):
    EN_CURSO = "EN_CURSO"
    ENTREGADO = "ENTREGADO"
    RETORNANDO = "RETORNANDO"
    FINALIZADO = "FINALIZADO"


class TipoIncidencia(StrEnum):
    BATERIA_BAJA = "BATERIA_BAJA"
    SENSOR_EN_FALLA = "SENSOR_EN_FALLA"
    RETRASO = "RETRASO"
    SALIDA_DE_ZONA = "SALIDA_DE_ZONA"
    ORDEN_RETORNO = "ORDEN_RETORNO"
    PARADA_EMERGENCIA = "PARADA_EMERGENCIA"
    ENTREGA_NO_CONFIRMADA = "ENTREGA_NO_CONFIRMADA"


class TipoAlerta(StrEnum):
    SERVICIO = "SERVICIO"
    MANTENIMIENTO = "MANTENIMIENTO"


class CausaAlerta(StrEnum):
    BATERIA_BAJA = "BATERIA_BAJA"
    SENSOR_EN_FALLA = "SENSOR_EN_FALLA"
    RETRASO = "RETRASO"
    SALIDA_DE_ZONA = "SALIDA_DE_ZONA"


class TipoOrden(StrEnum):
    """Órdenes de RF14 (no es un tipo de la base: se registran como incidencia)."""

    RETORNO_BASE = "RETORNO_BASE"
    PARADA_EMERGENCIA = "PARADA_EMERGENCIA"


def tipo_pg(enum: type[StrEnum], nombre: str) -> ENUM:
    """Tipo ENUM de PostgreSQL ya existente (``create_type=False``)."""
    return ENUM(enum, name=nombre, create_type=False, values_callable=lambda e: [m.value for m in e])


PG_ROL_USUARIO = tipo_pg(RolUsuario, "rol_usuario")
PG_ESTADO_USUARIO = tipo_pg(EstadoUsuario, "estado_usuario")
PG_ACCION_AUDITORIA = tipo_pg(AccionAuditoria, "accion_auditoria")
PG_TIPO_DISPOSITIVO = tipo_pg(TipoDispositivo, "tipo_dispositivo")
PG_ESTADO_DISPOSITIVO = tipo_pg(EstadoDispositivo, "estado_dispositivo")
PG_ESTADO_SENSOR = tipo_pg(EstadoSensor, "estado_sensor")
PG_TIPO_MANTENIMIENTO = tipo_pg(TipoMantenimiento, "tipo_mantenimiento")
PG_TIPO_SERVICIO = tipo_pg(TipoServicio, "tipo_servicio")
PG_ESTADO_RESERVA = tipo_pg(EstadoReserva, "estado_reserva")
PG_ESTADO_SERVICIO = tipo_pg(EstadoServicio, "estado_servicio")
PG_TIPO_INCIDENCIA = tipo_pg(TipoIncidencia, "tipo_incidencia")
PG_TIPO_ALERTA = tipo_pg(TipoAlerta, "tipo_alerta")
PG_CAUSA_ALERTA = tipo_pg(CausaAlerta, "causa_alerta")
