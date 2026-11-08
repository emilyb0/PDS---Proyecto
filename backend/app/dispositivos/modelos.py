"""Dispositivo, Robot, Drone y Sensor → tablas ``dispositivo`` y ``sensor`` (RF01–RF04, RF07, RNF10).

Robot y Drone son subclases con herencia de tabla única (``dispositivo.tipo`` es el discriminador).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Identity, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.nucleo.bd import Base
from app.nucleo.enums import (
    PG_ESTADO_DISPOSITIVO,
    PG_ESTADO_SENSOR,
    PG_TIPO_DISPOSITIVO,
    EstadoDispositivo,
    EstadoSensor,
    TipoDispositivo,
)

# Sensores que se crean si no se indican al registrar (especificación 7.2).
SENSORES_POR_TIPO = {
    TipoDispositivo.ROBOT: ["GPS", "Cámara", "LIDAR", "Ultrasonido"],
    TipoDispositivo.DRONE: ["GPS", "Cámara", "IMU", "Barómetro"],
}


class Sensor(Base):
    __tablename__ = "sensor"

    id_sensor: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_dispositivo: Mapped[int] = mapped_column(Integer, ForeignKey("dispositivo.id_dispositivo", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(60))
    estado: Mapped[EstadoSensor] = mapped_column(PG_ESTADO_SENSOR, default=EstadoSensor.OK)

    @property
    def en_falla(self) -> bool:
        return self.estado == EstadoSensor.FALLA


class Dispositivo(Base):
    """Clase abstracta del diagrama; las instancias son ``Robot`` o ``Drone``."""

    __tablename__ = "dispositivo"

    id_dispositivo: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tipo: Mapped[TipoDispositivo] = mapped_column(PG_TIPO_DISPOSITIVO)
    numero_serie: Mapped[str] = mapped_column(String(50))
    modelo: Mapped[str] = mapped_column(String(80))
    estado: Mapped[EstadoDispositivo] = mapped_column(PG_ESTADO_DISPOSITIVO, default=EstadoDispositivo.DISPONIBLE)
    nivel_bateria: Mapped[int] = mapped_column(SmallInteger, default=100)
    horas_uso_desde_mant: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"))
    capacidad_carga_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    autonomia_vuelo_min: Mapped[int | None] = mapped_column(SmallInteger)
    fecha_registro: Mapped[date] = mapped_column(Date)
    fecha_baja: Mapped[date | None] = mapped_column(Date)
    motivo_baja: Mapped[str | None] = mapped_column(String(255))

    sensores: Mapped[list[Sensor]] = relationship(
        order_by=Sensor.id_sensor, cascade="all, delete-orphan", lazy="selectin"
    )

    __mapper_args__ = {"polymorphic_on": "tipo", "polymorphic_abstract": True}

    # ------------------------------------------------------------------ reglas del diagrama

    @property
    def dado_de_baja(self) -> bool:
        return self.fecha_baja is not None

    def tiene_sensor_en_falla(self) -> bool:
        return any(sensor.en_falla for sensor in self.sensores)

    def sensores_en_falla(self) -> list[str]:
        return [sensor.nombre for sensor in self.sensores if sensor.en_falla]

    def motivos_estado(self) -> list[str]:
        """Motivos por los que no se le asigna ni se inicia un servicio: baja, mantenimiento o fuera de servicio."""
        if self.dado_de_baja:
            return [f"El dispositivo {self.numero_serie} está dado de baja"]
        if self.estado == EstadoDispositivo.EN_MANTENIMIENTO:
            return [f"El dispositivo {self.numero_serie} está en mantenimiento"]
        if self.estado == EstadoDispositivo.FUERA_DE_SERVICIO:
            return [f"El dispositivo {self.numero_serie} está fuera de servicio"]
        return []

    def motivos_no_apto(self, bateria_minima: int = 30) -> list[str]:
        """Motivos de RF07: batería menor al mínimo o sensores en falla. Lista vacía = apto."""
        motivos = []
        if self.nivel_bateria < bateria_minima:
            motivos.append(f"Batería {self.nivel_bateria} % (mínimo {bateria_minima} %)")
        motivos.extend(f"Sensor {nombre} en falla" for nombre in self.sensores_en_falla())
        return motivos

    def esta_apto(self, bateria_minima: int = 30) -> bool:
        """RF07: batería ≥ mínimo y ningún sensor en falla."""
        return not self.motivos_no_apto(bateria_minima)

    def actualizar_lectura(self, nivel_bateria: int, sensores: dict[str, EstadoSensor]) -> None:
        """Guarda la última lectura del dispositivo (RF07, RF09): batería y estado de cada sensor."""
        self.nivel_bateria = nivel_bateria
        for sensor in self.sensores:
            if sensor.nombre in sensores:
                sensor.estado = sensores[sensor.nombre]

    def requiere_mantenimiento(self, ultimo_mantenimiento: date, hoy: date, dias: int = 30, horas: float = 50) -> bool:
        """RF16: 30 días o 50 h de uso desde el último mantenimiento, lo que ocurra primero."""
        return (hoy - ultimo_mantenimiento).days >= dias or float(self.horas_uso_desde_mant) >= horas

    def editar(
        self,
        modelo: str | None = None,
        estado: EstadoDispositivo | None = None,
        capacidad_carga_kg: Decimal | None = None,
        autonomia_vuelo_min: int | None = None,
    ) -> None:
        """RF02: cambia modelo, capacidad o autonomía (según el tipo) y estado manual. Las reglas van en el servicio."""
        if modelo is not None:
            self.modelo = modelo
        if estado is not None:
            self.estado = estado
        if capacidad_carga_kg is not None:
            self.capacidad_carga_kg = capacidad_carga_kg
        if autonomia_vuelo_min is not None:
            self.autonomia_vuelo_min = autonomia_vuelo_min

    def dar_de_baja(self, motivo: str, fecha: date) -> None:
        """RF03: queda fuera de servicio y excluido de nuevas asignaciones (las reservas se validan antes)."""
        self.fecha_baja = fecha
        self.motivo_baja = motivo
        self.estado = EstadoDispositivo.FUERA_DE_SERVICIO

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.id_dispositivo} {self.numero_serie} {self.estado}>"


class Robot(Dispositivo):
    __mapper_args__ = {"polymorphic_identity": TipoDispositivo.ROBOT}


class Drone(Dispositivo):
    __mapper_args__ = {"polymorphic_identity": TipoDispositivo.DRONE}


CLASE_POR_TIPO: dict[TipoDispositivo, type[Dispositivo]] = {
    TipoDispositivo.ROBOT: Robot,
    TipoDispositivo.DRONE: Drone,
}
