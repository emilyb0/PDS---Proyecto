"""Puntos de extensión del núcleo para los módulos removibles (CLAUDE.md, "Entregas: núcleo y módulos por RF").

El núcleo (entrega 1: RF01, RF04–RF12, RF18, RF20) nunca importa un módulo. Cada módulo de la entrega 2 vive en
``app/modulos/rfXX_nombre/``, expone ``MODULO = ModuloRF(...)`` y, en ``configurar``, se engancha aquí.
Si un módulo se borra o se apaga (``MODULOS_ACTIVOS``), el núcleo sigue funcionando igual, sin ese comportamiento.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import APIRouter

from app.nucleo.enums import RolUsuario

# Requisitos de la entrega 1: no son removibles.
REQUISITOS_NUCLEO = ("RF01", "RF04", "RF05", "RF06", "RF07", "RF08", "RF09", "RF10", "RF11", "RF12", "RF18", "RF20")

# Las funciones reciben el Contenedor (u otros objetos del núcleo); se tipan como Any para no crear ciclos.
FuncionAsync = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class TareaProgramada:
    """Tarea periódica. ``funcion(contenedor)`` se ejecuta según el disparador (APScheduler, zona de Colombia)."""

    nombre: str  # también es el nombre en /api/demo/tareas/{nombre}/ejecutar
    funcion: FuncionAsync
    tipo: Literal["intervalo", "diaria"]
    segundos: float | None = None  # para "intervalo"
    hora: int | None = None  # para "diaria" (hora local)
    minuto: int = 0
    ejecutable_en_demo: bool = True


@dataclass
class Extensiones:
    """Registro de lo que aportan los módulos activos. El núcleo lo recorre en cada punto de extensión."""

    # Reservas: validaciones extra después de RF06 y RF07, al crear y al reprogramar. Firma:
    # (ContextoReserva) -> list[Advertencia]; para rechazar, lanzan un ErrorAplicacion. RF23: clima.
    validadores_reserva: list[FuncionAsync] = field(default_factory=list)
    # Evaluador de clima opcional para otros módulos: (contenedor, ubicacion, inicio, fin) -> EvaluacionClima.
    # Lo registra RF23; RF22 lo usa si existe.
    evaluador_clima: FuncionAsync | None = None
    # Servicio en curso (Fase 4).
    ajustes_orden_inicio: list[Callable[..., Any]] = field(default_factory=list)  # RF24: el robot espera código
    verificaciones_monitor: list[FuncionAsync] = field(default_factory=list)  # RF25: salida de zona
    manejadores_evento: dict[str, FuncionAsync] = field(default_factory=dict)  # RF24: CODIGO_INGRESADO
    # (sesion, contenedor, id_dispositivo) -> alertas creadas en la transacción del cierre; el núcleo las
    # publica por SSE después del commit. RF16: revisión preventiva.
    al_finalizar_servicio: list[FuncionAsync] = field(default_factory=list)
    # Tareas programadas y controles de demo.
    tareas: list[TareaProgramada] = field(default_factory=list)
    eventos_demo: dict[str, FuncionAsync] = field(default_factory=dict)  # RF25: SALIR/VOLVER zona
    # /health y menú del frontend.
    chequeos_salud: dict[str, FuncionAsync] = field(default_factory=dict)
    funciones: dict[RolUsuario, list[str]] = field(
        default_factory=lambda: {RolUsuario.ADMINISTRADOR: [], RolUsuario.OPERADOR: []}
    )
    # Objetos propios de cada módulo (por ejemplo, el servicio de clima de RF23), por nombre.
    servicios: dict[str, Any] = field(default_factory=dict)

    def agregar_funciones(self, *funciones: str, solo_administrador: bool = False) -> None:
        """Funciones de menú que aporta un módulo (el administrador siempre las recibe)."""
        roles = [RolUsuario.ADMINISTRADOR] if solo_administrador else list(RolUsuario)
        for rol in roles:
            self.funciones[rol].extend(f for f in funciones if f not in self.funciones[rol])


@dataclass(frozen=True)
class ModuloRF:
    """Un requisito removible de la entrega 2."""

    clave: str  # "rf15"
    requisitos: tuple[str, ...]  # ("RF15",)
    nombre: str  # "Registrar mantenimiento"
    routers: tuple[APIRouter, ...] = ()
    etiquetas_openapi: tuple[dict[str, str], ...] = ()
    # configurar(extensiones, config): engancha el módulo; recibe la Configuracion para crear sus servicios.
    configurar: Callable[[Extensiones, Any], None] | None = None
