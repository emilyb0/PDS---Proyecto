"""``IApiDispositivo``: cómo el servidor habla con un robot o drone (RF07, RF09, RF14, RF24; RESTR01).

Cambios frente al diagrama (decisión D2): cada método recibe ``numero_serie`` (un solo simulador atiende todos
los dispositivos), ``enviar_orden_inicio`` recibe una ``OrdenInicio`` en vez de la entidad ``Reserva``, y se
agregan ``confirmar_entrega`` y ``esperar_evento``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.nucleo.enums import EstadoSensor, TipoOrden, TipoServicio


class Fase(StrEnum):
    """Fase que reporta el dispositivo (va en ``estado_servicio`` de la telemetría)."""

    EN_BASE = "EN_BASE"
    EN_RUTA = "EN_RUTA"
    EN_DESTINO = "EN_DESTINO"
    ESPERANDO_CODIGO = "ESPERANDO_CODIGO"
    RETORNANDO = "RETORNANDO"
    DETENIDO = "DETENIDO"


class TipoEvento(StrEnum):
    """Avisos que el dispositivo envía al servidor (flechas Dispositivo → Servidor del diagrama de secuencia)."""

    CODIGO_INGRESADO = "CODIGO_INGRESADO"
    LLEGADA_BASE = "LLEGADA_BASE"


class ResultadoEntrega(StrEnum):
    CONFIRMADA = "CONFIRMADA"  # código correcto: el robot regresa
    NO_CONFIRMADA = "NO_CONFIRMADA"  # código incorrecto: el robot sigue esperando
    AGOTADA = "AGOTADA"  # se agotaron los intentos o el tiempo: regresa sin entregar


@dataclass(frozen=True)
class Punto:
    latitud: float
    longitud: float
    nombre: str = ""


@dataclass(frozen=True)
class TelemetriaDispositivo:
    """Lo que responde el dispositivo (``RegistroTelemetria`` del diagrama)."""

    numero_serie: str
    fecha_hora: datetime
    latitud: float
    longitud: float
    nivel_bateria: int
    sensores: dict[str, EstadoSensor]
    estado_servicio: Fase


@dataclass(frozen=True)
class Reanudacion:
    """Datos para retomar un servicio abierto después de reiniciar el backend (decisión P1).

    El dispositivo sigue desde su último punto guardado; si no hay puntos, sale otra vez desde la base.
    """

    hora_salida: datetime
    ultimo_punto: Punto | None = None
    hora_ultimo_punto: datetime | None = None
    fase_reportada: Fase | None = None
    regresando: bool = False  # la bitácora ya está ENTREGADO o RETORNANDO: va directo a la base


@dataclass(frozen=True)
class OrdenInicio:
    """Lo que el dispositivo necesita saber de la reserva para salir."""

    id_reserva: int
    tipo_servicio: TipoServicio
    origen: Punto
    destino: Punto
    inicio: datetime
    duracion_estimada_min: int
    esperar_codigo: bool = False  # RF24 lo activa con Extensiones.ajustes_orden_inicio
    reanudacion: Reanudacion | None = None


@dataclass(frozen=True)
class EventoDispositivo:
    numero_serie: str
    tipo: TipoEvento
    fecha_hora: datetime
    datos: dict[str, str] = field(default_factory=dict)


class ErrorDispositivo(Exception):
    """El dispositivo no respondió o rechazó la orden."""


class IApiDispositivo(ABC):
    @abstractmethod
    async def obtener_telemetria(self, numero_serie: str) -> TelemetriaDispositivo:
        """Ubicación, batería, sensores y fase actuales (RF07, RF09)."""

    @abstractmethod
    async def enviar_orden_inicio(self, numero_serie: str, orden: OrdenInicio) -> None:
        """Inicia el servicio (paso 29 del diagrama de secuencia)."""

    @abstractmethod
    async def enviar_orden(self, numero_serie: str, tipo: TipoOrden) -> None:
        """Retorno a base o parada de emergencia (RF14)."""

    @abstractmethod
    async def leer_codigo_entrega(self, numero_serie: str) -> str | None:
        """Último código digitado por quien recibe (RF24)."""

    @abstractmethod
    async def confirmar_entrega(self, numero_serie: str, resultado: ResultadoEntrega) -> None:
        """Le dice al robot el resultado de la entrega (agregado; especificación 7.5)."""

    @abstractmethod
    async def descargar_video(self, numero_serie: str) -> bytes:
        """MP4 del recorrido al llegar a la base (RF12)."""

    @abstractmethod
    async def esperar_evento(self) -> EventoDispositivo:
        """Espera el siguiente aviso del dispositivo (``CODIGO_INGRESADO`` o ``LLEGADA_BASE``)."""
