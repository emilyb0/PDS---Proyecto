"""Esquemas del inventario de dispositivos del núcleo (RF01, RF04). RF02 y RF03 (pendientes) traerán los suyos."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.dispositivos.modelos import Dispositivo
from app.nucleo.enums import EstadoDispositivo, EstadoSensor, TipoDispositivo
from app.nucleo.esquemas import Advertencia, EsquemaEntrada, FechaHora

# Estados que se pueden fijar a mano (especificación 7.2); EN_SERVICIO y EN_MANTENIMIENTO los maneja el sistema.
ESTADOS_MANUALES = (EstadoDispositivo.DISPONIBLE, EstadoDispositivo.EN_CARGA, EstadoDispositivo.FUERA_DE_SERVICIO)
_TEXTO_ESTADOS_MANUALES = "DISPONIBLE, EN_CARGA o FUERA_DE_SERVICIO"


def validar_estado_manual(estado: EstadoDispositivo | None) -> EstadoDispositivo | None:
    if estado is not None and estado not in ESTADOS_MANUALES:
        raise ValueError(f"El estado {estado.value} lo maneja el sistema; use {_TEXTO_ESTADOS_MANUALES}.")
    return estado


# ============================================================================ entrada


class DispositivoCrear(EsquemaEntrada):
    tipo: TipoDispositivo
    numero_serie: str = Field(min_length=1, max_length=50, examples=["R-005"])
    modelo: str = Field(min_length=1, max_length=80, examples=["Rover Mk2"])
    capacidad_carga_kg: float | None = Field(default=None, gt=0, le=9999.99, description="Solo robots")
    autonomia_vuelo_min: int | None = Field(default=None, gt=0, le=32767, description="Solo drones")
    estado: EstadoDispositivo = EstadoDispositivo.DISPONIBLE
    sensores: list[str] | None = Field(
        default=None, min_length=1, description="Nombres de los sensores; si se omite, se crean los del tipo"
    )

    @field_validator("numero_serie")
    @classmethod
    def _serie_en_mayusculas(cls, valor: str) -> str:
        return valor.strip().upper()

    @field_validator("estado")
    @classmethod
    def _estado_inicial(cls, valor: EstadoDispositivo) -> EstadoDispositivo:
        return validar_estado_manual(valor) or valor

    @field_validator("sensores")
    @classmethod
    def _sensores_validos(cls, valor: list[str] | None) -> list[str] | None:
        if valor is None:
            return None
        limpios = [nombre.strip() for nombre in valor]
        if any(not nombre or len(nombre) > 60 for nombre in limpios):
            raise ValueError("Cada sensor debe tener un nombre de 1 a 60 caracteres.")
        if len({nombre.lower() for nombre in limpios}) != len(limpios):
            raise ValueError("Hay sensores repetidos.")
        return limpios

    @model_validator(mode="after")
    def _datos_del_tipo(self) -> DispositivoCrear:
        if self.tipo == TipoDispositivo.ROBOT:
            if self.capacidad_carga_kg is None:
                raise ValueError("Un robot requiere la capacidad de carga en kilogramos (capacidad_carga_kg).")
            if self.autonomia_vuelo_min is not None:
                raise ValueError("La autonomía de vuelo no aplica a los robots.")
        else:
            if self.autonomia_vuelo_min is None:
                raise ValueError("Un drone requiere la autonomía de vuelo en minutos (autonomia_vuelo_min).")
            if self.capacidad_carga_kg is not None:
                raise ValueError("La capacidad de carga no aplica a los drones.")
        return self


# ============================================================================ salida


class SensorSalida(BaseModel):
    id_sensor: int
    nombre: str
    estado: EstadoSensor


class DispositivoResumen(BaseModel):
    id_dispositivo: int
    numero_serie: str
    tipo: TipoDispositivo
    modelo: str

    @classmethod
    def de(cls, dispositivo: Dispositivo) -> DispositivoResumen:
        return cls(
            id_dispositivo=dispositivo.id_dispositivo,
            numero_serie=dispositivo.numero_serie,
            tipo=dispositivo.tipo,
            modelo=dispositivo.modelo,
        )


class DispositivoSalida(BaseModel):
    id_dispositivo: int
    tipo: TipoDispositivo
    numero_serie: str
    modelo: str
    estado: EstadoDispositivo
    nivel_bateria: int
    horas_uso_desde_mant: float
    capacidad_carga_kg: float | None
    autonomia_vuelo_min: int | None
    fecha_registro: date
    dado_de_baja: bool
    fecha_baja: date | None
    motivo_baja: str | None
    sensores_en_falla: list[str]

    @classmethod
    def de(cls, d: Dispositivo) -> DispositivoSalida:
        return cls(
            id_dispositivo=d.id_dispositivo,
            tipo=d.tipo,
            numero_serie=d.numero_serie,
            modelo=d.modelo,
            estado=d.estado,
            nivel_bateria=d.nivel_bateria,
            horas_uso_desde_mant=float(d.horas_uso_desde_mant),
            capacidad_carga_kg=None if d.capacidad_carga_kg is None else float(d.capacidad_carga_kg),
            autonomia_vuelo_min=d.autonomia_vuelo_min,
            fecha_registro=d.fecha_registro,
            dado_de_baja=d.dado_de_baja,
            fecha_baja=d.fecha_baja,
            motivo_baja=d.motivo_baja,
            sensores_en_falla=d.sensores_en_falla(),
        )


class ServicioActivo(BaseModel):
    id_bitacora: int
    id_reserva: int
    estado: str


class TelemetriaResumen(BaseModel):
    fecha_hora: FechaHora
    latitud: float
    longitud: float
    nivel_bateria: int
    estado_servicio: str


class DispositivoDetalle(DispositivoSalida):
    sensores: list[SensorSalida]
    servicio_activo: ServicioActivo | None = None
    ultima_telemetria: TelemetriaResumen | None = None
    advertencias: list[Advertencia] = Field(default_factory=list)
