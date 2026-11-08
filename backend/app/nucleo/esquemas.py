"""Tipos y esquemas Pydantic comunes: fechas en hora de Colombia, horas HH:MM, paginación y advertencias."""

from __future__ import annotations

from datetime import datetime, time
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer

from app.nucleo.reloj import a_hora_local, con_zona


def _serializar_fecha_hora(valor: datetime) -> str:
    return con_zona(valor).isoformat()


def _hora_sin_segundos(valor: time) -> time:
    return valor.replace(second=0, microsecond=0, tzinfo=None)


# Fecha y hora: se acepta con o sin zona (sin zona = Colombia) y se devuelve con -05:00 (decisión T7).
FechaHora = Annotated[
    datetime,
    AfterValidator(a_hora_local),
    PlainSerializer(_serializar_fecha_hora, return_type=str, when_used="json"),
]

# Hora del día en formato HH:MM (decisión D12: sin segundos).
Hora = Annotated[
    time,
    AfterValidator(_hora_sin_segundos),
    PlainSerializer(lambda valor: valor.strftime("%H:%M"), return_type=str, when_used="json"),
]


class Esquema(BaseModel):
    """Base de los esquemas de respuesta: se arman desde los modelos de SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


class EsquemaEntrada(BaseModel):
    """Base de los cuerpos de petición: rechaza campos desconocidos (por ejemplo, ``tipo`` al editar)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Advertencia(BaseModel):
    codigo: str
    mensaje: str
    detalles: dict[str, Any] | None = None


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    limite: int
    desplazamiento: int


class ParametrosPaginacion(BaseModel):
    limite: int = Field(default=50, ge=1, le=200)
    desplazamiento: int = Field(default=0, ge=0)
