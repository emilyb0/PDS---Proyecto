"""Errores de la aplicación, traducción de errores de PostgreSQL y formato único de error.

Formato (especificación, sección 9)::

    {"error": {"codigo": "CRUCE_HORARIO", "mensaje": "…", "detalles": {…}}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

registro = logging.getLogger(__name__)


# ============================================================================ Excepciones


class ErrorAplicacion(Exception):
    """Error con código y mensaje para el usuario."""

    estado_http: int = 409
    codigo: str = "REGLA_NEGOCIO"

    def __init__(
        self,
        mensaje: str,
        detalles: dict[str, Any] | None = None,
        *,
        codigo: str | None = None,
        estado_http: int | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles
        if codigo is not None:
            self.codigo = codigo
        if estado_http is not None:
            self.estado_http = estado_http


class ErrorValidacion(ErrorAplicacion):
    estado_http = 422
    codigo = "VALIDACION"

    @classmethod
    def de_campo(cls, campo: str, mensaje: str) -> ErrorValidacion:
        return cls(mensaje, {"campos": [{"campo": campo, "mensaje": mensaje}]})


class ErrorNoAutenticado(ErrorAplicacion):
    estado_http = 401
    codigo = "NO_AUTENTICADO"


class ErrorSinPermiso(ErrorAplicacion):
    estado_http = 403
    codigo = "SIN_PERMISO"


class ErrorNoEncontrado(ErrorAplicacion):
    estado_http = 404
    codigo = "NO_ENCONTRADO"


class ErrorDuplicado(ErrorAplicacion):
    codigo = "DUPLICADO"


class ErrorCruceHorario(ErrorAplicacion):
    codigo = "CRUCE_HORARIO"


class ErrorDispositivoNoApto(ErrorAplicacion):
    codigo = "DISPOSITIVO_NO_APTO"


class ErrorClimaNoApto(ErrorAplicacion):
    codigo = "CLIMA_NO_APTO"


class ErrorTipoDispositivoIncorrecto(ErrorAplicacion):
    codigo = "TIPO_DISPOSITIVO_INCORRECTO"


class ErrorReservasPendientes(ErrorAplicacion):
    codigo = "RESERVAS_PENDIENTES"


class ErrorReglaNegocio(ErrorAplicacion):
    codigo = "REGLA_NEGOCIO"


class ErrorServicioNoDisponible(ErrorAplicacion):
    estado_http = 503
    codigo = "SERVICIO_NO_DISPONIBLE"


# ============================================================ Traducción de errores de PostgreSQL (sección 4)

MENSAJES_UNICOS = {
    "uq_usuario_correo": "Ya existe un usuario con ese correo institucional.",
    "dispositivo_numero_serie_key": "Ya existe un dispositivo con ese número de serie.",
    "uq_sensor_nombre": "El dispositivo ya tiene un sensor con ese nombre.",
    "ubicacion_nombre_key": "Ya existe una ubicación con ese nombre.",
    "zona_operacion_nombre_key": "Ya existe una zona de operación con ese nombre.",
    "bitacora_servicio_id_reserva_key": "La reserva ya tiene una bitácora de servicio.",
    "alerta_servicio_id_incidencia_key": "La incidencia ya tiene una alerta asociada.",
    "atencion_alerta_id_alerta_key": "La alerta ya fue atendida.",
    "video_id_bitacora_key": "El servicio ya tiene un video asociado.",
    "uq_telemetria_punto": "Ya existe un punto de telemetría para ese instante.",
}

MENSAJES_CHECK = {
    "ck_disp_bateria": "El nivel de batería debe estar entre 0 y 100.",
    "ck_disp_horas": "Las horas de uso no pueden ser negativas.",
    "ck_disp_carga": "La capacidad de carga debe ser mayor que 0.",
    "ck_disp_vuelo": "La autonomía de vuelo debe ser mayor que 0.",
    "ck_disp_subtipo": "Un robot lleva capacidad de carga (kg) y un drone, autonomía de vuelo (min); no ambos.",
    "ck_disp_baja": "La baja requiere fecha y motivo.",
    "ck_mant_fechas": "La fecha de fin del mantenimiento no puede ser anterior a la de inicio.",
    "ubicacion_latitud_check": "La latitud debe estar entre -90 y 90.",
    "ubicacion_longitud_check": "La longitud debe estar entre -180 y 180.",
    "vertice_zona_orden_check": "El orden de los vértices empieza en 1.",
    "reserva_duracion_estimada_min_check": "La duración estimada debe ser mayor que 0.",
    "reserva_codigo_entrega_check": "El código de entrega debe tener 4 dígitos.",
    "ck_reserva_motivo": "Para cancelar una reserva hay que indicar el motivo.",
    "ck_bit_regreso": "La hora de regreso no puede ser anterior a la de salida.",
    "ck_bit_entrega": "La hora de entrega no puede ser anterior a la de salida.",
    "ck_bit_entregado": "Un servicio entregado debe tener hora de entrega.",
    "ck_bit_cierre": "La bitácora se finaliza si y solo si tiene hora de regreso.",
    "registro_telemetria_nivel_bateria_check": "El nivel de batería debe estar entre 0 y 100.",
    "ck_inc_ubicacion": "La incidencia debe tener latitud y longitud, o ninguna de las dos.",
    "ck_inc_zona": "Una salida de zona debe registrar la ubicación del dispositivo.",
    "alerta_mantenimiento_dias_desde_ultimo_check": "Los días desde el último mantenimiento no pueden ser negativos.",
    "alerta_mantenimiento_horas_desde_ultimo_check": "Las horas desde el último mantenimiento no pueden ser negativas.",
    "video_formato_check": "El video debe estar en formato MP4.",
    "video_duracion_seg_check": "La duración del video debe ser mayor que 0.",
    "ck_video_eliminacion": "La fecha de eliminación no puede ser anterior a la de grabación.",
}

MENSAJES_FK = {
    "reserva_id_administrador_fkey": "El administrador indicado no existe.",
    "reserva_id_operador_fkey": "El operador indicado no existe.",
    "reserva_id_dispositivo_fkey": "El dispositivo indicado no existe.",
    "reserva_id_origen_fkey": "La ubicación de origen no existe.",
    "reserva_id_destino_fkey": "La ubicación de destino no existe.",
    "mantenimiento_id_operador_fkey": "El operador responsable no existe.",
    "mantenimiento_id_dispositivo_fkey": "El dispositivo indicado no existe.",
    "atencion_alerta_id_alerta_fkey": "Solo se atienden alertas de servicio existentes.",
    "atencion_alerta_id_operador_fkey": "El operador indicado no existe.",
}


def traducir_error_bd(error: DBAPIError) -> ErrorAplicacion | None:
    """Convierte un error de PostgreSQL en un ``ErrorAplicacion``. Devuelve ``None`` si no lo reconoce."""
    original = getattr(error, "orig", None)
    sqlstate = getattr(original, "sqlstate", None)
    diag = getattr(original, "diag", None)
    restriccion = getattr(diag, "constraint_name", None) or ""
    mensaje_bd = getattr(diag, "message_primary", None) or str(original)

    if sqlstate == "23P01":
        return ErrorCruceHorario("El horario se cruza con otra reserva activa del dispositivo.")
    if sqlstate == "23505":
        return ErrorDuplicado(MENSAJES_UNICOS.get(restriccion, "Ya existe un registro con esos datos."))
    if sqlstate == "23514":
        return ErrorReglaNegocio(
            MENSAJES_CHECK.get(restriccion, "Los datos no cumplen una regla del sistema."),
            {"restriccion": restriccion} if restriccion else None,
        )
    if sqlstate == "P0001":
        return ErrorReglaNegocio(mensaje_bd)
    if sqlstate == "23503":
        return ErrorNoEncontrado(MENSAJES_FK.get(restriccion, "Uno de los registros indicados no existe."))
    return None


def es_error_bd(error: BaseException, sqlstate: str, restriccion: str | None = None) -> bool:
    """Indica si ``error`` es un error de PostgreSQL con ese SQLSTATE (y esa restricción, si se indica)."""
    original = getattr(error, "orig", None)
    if getattr(original, "sqlstate", None) != sqlstate:
        return False
    if restriccion is None:
        return True
    return getattr(getattr(original, "diag", None), "constraint_name", None) == restriccion


# ============================================================================ Respuestas


def respuesta_error(
    estado: int,
    codigo: str,
    mensaje: str,
    detalles: dict[str, Any] | None = None,
    cabeceras: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=estado,
        content={"error": {"codigo": codigo, "mensaje": mensaje, "detalles": detalles}},
        headers=cabeceras,
    )


def _respuesta_de(error: ErrorAplicacion) -> JSONResponse:
    cabeceras = {"WWW-Authenticate": "Bearer"} if error.estado_http == 401 else None
    return respuesta_error(error.estado_http, error.codigo, error.mensaje, error.detalles, cabeceras)


# Mensajes en español para los errores de validación de Pydantic más comunes.
_MENSAJES_VALIDACION = {
    "missing": "Campo obligatorio.",
    "extra_forbidden": "Campo no permitido.",
    "string_too_short": "Debe tener al menos {min_length} caracteres.",
    "string_too_long": "Debe tener como máximo {max_length} caracteres.",
    "string_type": "Debe ser un texto.",
    "string_pattern_mismatch": "El formato no es válido.",
    "int_parsing": "Debe ser un número entero.",
    "int_type": "Debe ser un número entero.",
    "int_from_float": "Debe ser un número entero.",
    "float_parsing": "Debe ser un número.",
    "float_type": "Debe ser un número.",
    "decimal_parsing": "Debe ser un número.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "bool_type": "Debe ser verdadero o falso.",
    "greater_than": "Debe ser mayor que {gt}.",
    "greater_than_equal": "Debe ser mayor o igual a {ge}.",
    "less_than": "Debe ser menor que {lt}.",
    "less_than_equal": "Debe ser menor o igual a {le}.",
    "enum": "Valor no válido. Use uno de: {expected}.",
    "literal_error": "Valor no válido. Use uno de: {expected}.",
    "date_parsing": "Fecha no válida; use el formato AAAA-MM-DD.",
    "date_from_datetime_parsing": "Fecha no válida; use el formato AAAA-MM-DD.",
    "date_type": "Fecha no válida; use el formato AAAA-MM-DD.",
    "time_parsing": "Hora no válida; use el formato HH:MM.",
    "time_type": "Hora no válida; use el formato HH:MM.",
    "datetime_parsing": "Fecha y hora no válidas; use ISO 8601.",
    "datetime_from_date_parsing": "Fecha y hora no válidas; use ISO 8601.",
    "datetime_type": "Fecha y hora no válidas; use ISO 8601.",
    "json_invalid": "El cuerpo no es un JSON válido.",
    "model_attributes_type": "Se esperaba un objeto JSON.",
    "dict_type": "Se esperaba un objeto JSON.",
    "list_type": "Se esperaba una lista.",
    "too_short": "Debe tener al menos {min_length} elementos.",
    "too_long": "Debe tener como máximo {max_length} elementos.",
}


def _mensaje_validacion(error: dict[str, Any]) -> str:
    tipo = error.get("type", "")
    contexto = error.get("ctx") or {}
    if tipo == "value_error":
        # Mensajes de nuestros validadores: se quita el prefijo que agrega Pydantic.
        mensaje = str(contexto.get("error") or error.get("msg", ""))
        return mensaje.removeprefix("Value error, ")
    if tipo.startswith("value_error") and "email" in str(error.get("msg", "")).lower():
        return "Correo no válido."
    plantilla = _MENSAJES_VALIDACION.get(tipo)
    if plantilla is None:
        return str(error.get("msg", "Valor no válido."))
    try:
        return plantilla.format(**contexto)
    except (KeyError, IndexError):
        return plantilla


def _campos_validacion(errores: list[dict[str, Any]]) -> list[dict[str, str]]:
    campos = []
    for error in errores:
        ubicacion = [str(parte) for parte in error.get("loc", ()) if parte not in ("body", "query", "path")]
        campos.append({"campo": ".".join(ubicacion) or "cuerpo", "mensaje": _mensaje_validacion(error)})
    return campos


_CODIGOS_HTTP = {
    400: "VALIDACION",
    401: "NO_AUTENTICADO",
    403: "SIN_PERMISO",
    404: "NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
    409: "REGLA_NEGOCIO",
    422: "VALIDACION",
    503: "SERVICIO_NO_DISPONIBLE",
}

_MENSAJES_HTTP = {
    401: "Debe iniciar sesión.",
    403: "No tiene permiso para esta acción.",
    404: "No se encontró el recurso.",
    405: "Método no permitido en esta ruta.",
}


def registrar_manejadores(app: FastAPI) -> None:
    """Registra los manejadores que dan el formato único de error."""

    @app.exception_handler(ErrorAplicacion)
    async def _error_aplicacion(_: Request, error: ErrorAplicacion) -> JSONResponse:
        return _respuesta_de(error)

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        campos = _campos_validacion(list(error.errors()))
        mensaje = campos[0]["mensaje"] if len(campos) == 1 else "Hay datos inválidos en la solicitud."
        if len(campos) == 1 and campos[0]["campo"] != "cuerpo":
            mensaje = f"{campos[0]['campo']}: {campos[0]['mensaje']}"
        return respuesta_error(422, "VALIDACION", mensaje, {"campos": campos})

    @app.exception_handler(StarletteHTTPException)
    async def _error_http(_: Request, error: StarletteHTTPException) -> JSONResponse:
        codigo = _CODIGOS_HTTP.get(error.status_code, "ERROR_INTERNO" if error.status_code >= 500 else "VALIDACION")
        mensaje = (
            error.detail
            if isinstance(error.detail, str) and error.status_code not in _MENSAJES_HTTP
            else _MENSAJES_HTTP.get(error.status_code, str(error.detail))
        )
        return respuesta_error(error.status_code, codigo, mensaje, None, getattr(error, "headers", None))

    @app.exception_handler(DBAPIError)
    async def _error_bd(_: Request, error: DBAPIError) -> JSONResponse:
        traducido = traducir_error_bd(error)
        if traducido is not None:
            return _respuesta_de(traducido)
        if isinstance(error, OperationalError | InterfaceError) or error.connection_invalidated:
            registro.error("La base de datos no responde: %s", error)
            return respuesta_error(503, "SERVICIO_NO_DISPONIBLE", "La base de datos no está disponible.")
        registro.exception("Error de base de datos no traducido")
        return respuesta_error(500, "ERROR_INTERNO", "Ocurrió un error interno.")

    @app.exception_handler(Exception)
    async def _error_inesperado(_: Request, error: Exception) -> JSONResponse:
        registro.exception("Error no controlado: %s", type(error).__name__)
        return respuesta_error(500, "ERROR_INTERNO", "Ocurrió un error interno.")
