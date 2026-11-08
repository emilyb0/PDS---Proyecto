"""Controles de demo del núcleo (especificación, sección 9). Solo con ``MODO_DEMO=true`` y solo administrador.

Sirven para mostrar cada regla en la presentación sin esperar. No se auditan: simulan al dispositivo o al reloj
(decisión D13). Los módulos de la entrega 2 (pendientes) podrán agregar sus propios eventos
(``Extensiones.eventos_demo``; por ejemplo RF25: salir y volver a la zona) y tareas (``Extensiones.tareas``;
por ejemplo RF16 y RF26).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.dispositivos.servicio import obtener_dispositivo
from app.integraciones.dispositivo.interfaz import ErrorDispositivo
from app.integraciones.dispositivo.simulador import ApiDispositivoSimulada
from app.nucleo.dependencias import Administrador, ContenedorDep, ModoDemo, Sesion
from app.nucleo.errores import ErrorNoEncontrado, ErrorReglaNegocio, ErrorValidacion
from app.nucleo.esquemas import EsquemaEntrada
from app.tareas.catalogo import resumir, todas_las_tareas

router = APIRouter(prefix="/api/demo", tags=["Demo"])

EVENTOS_NUCLEO = ("BATERIA", "FALLA_SENSOR", "REPARAR_SENSOR", "PAUSAR", "REANUDAR")


class InicioSalida(BaseModel):
    resultado: str
    id_reserva: int
    id_bitacora: int | None


class EventoDemo(EsquemaEntrada):
    tipo: str = Field(examples=["BATERIA"], description="BATERIA, FALLA_SENSOR, REPARAR_SENSOR, PAUSAR, REANUDAR…")
    nivel: int | None = Field(default=None, ge=0, le=100, description="Para BATERIA")
    sensor: str | None = Field(default=None, max_length=60, description="Para FALLA_SENSOR y REPARAR_SENSOR")


class EventoDemoSalida(BaseModel):
    id_dispositivo: int
    numero_serie: str
    tipo: str
    mensaje: str


class TareaSalida(BaseModel):
    tarea: str
    resultado: Any


def _simulador(contenedor: Any) -> ApiDispositivoSimulada:
    simulador = contenedor.api_dispositivo
    if not isinstance(simulador, ApiDispositivoSimulada):
        raise ErrorReglaNegocio("Los controles de demo solo funcionan con el dispositivo simulado.")
    return simulador


@router.post(
    "/reservas/{id_reserva:int}/iniciar",
    response_model=InicioSalida,
    summary="Iniciar ya una reserva (demo)",
    description="Demo, RF08. Inicia ya el servicio de una reserva `PROGRAMADA`, con las mismas validaciones del "
    "inicio automático (dispositivo libre y apto); solo se salta la hora (decisión D15). Si no se puede, responde "
    "409 con el motivo.",
)
async def iniciar_reserva(id_reserva: int, _: ModoDemo, __: Administrador, contenedor: ContenedorDep) -> InicioSalida:
    resultado = await contenedor.monitor.iniciar_servicio(id_reserva, forzado=True)
    return InicioSalida(resultado=resultado.resultado, id_reserva=id_reserva, id_bitacora=resultado.id_bitacora)


@router.post(
    "/dispositivos/{id_dispositivo:int}/eventos",
    response_model=EventoDemoSalida,
    summary="Provocar un evento en el dispositivo simulado (demo)",
    description="Demo, RF07, RF11. `BATERIA` (con `nivel`), `FALLA_SENSOR` o `REPARAR_SENSOR` (con `sensor`), "
    "`PAUSAR` o `REANUDAR` (la pausa provoca un retraso). Los módulos activos pueden agregar otros. "
    "El efecto se ve en el siguiente ciclo de monitoreo.",
)
async def evento_dispositivo(
    id_dispositivo: int,
    datos: EventoDemo,
    _: ModoDemo,
    __: Administrador,
    sesion: Sesion,
    contenedor: ContenedorDep,
) -> EventoDemoSalida:
    simulador = _simulador(contenedor)
    dispositivo = await obtener_dispositivo(sesion, id_dispositivo)
    serie = dispositivo.numero_serie
    tipo = datos.tipo.strip().upper()
    extras = contenedor.extensiones.eventos_demo
    disponibles = [*EVENTOS_NUCLEO, *extras]
    try:
        if tipo == "BATERIA":
            if datos.nivel is None:
                raise ErrorValidacion.de_campo("nivel", "Indique el nivel de batería (0 a 100).")
            await simulador.fijar_bateria(serie, datos.nivel)
            mensaje = f"Batería de {serie} fijada en {datos.nivel} %."
        elif tipo in ("FALLA_SENSOR", "REPARAR_SENSOR"):
            if not datos.sensor:
                raise ErrorValidacion.de_campo("sensor", "Indique el nombre del sensor.")
            if tipo == "FALLA_SENSOR":
                await simulador.fallar_sensor(serie, datos.sensor)
                mensaje = f"Sensor {datos.sensor} de {serie} en falla."
            else:
                await simulador.reparar_sensor(serie, datos.sensor)
                mensaje = f"Sensor {datos.sensor} de {serie} reparado."
        elif tipo in ("PAUSAR", "REANUDAR"):
            await simulador.pausar(serie, tipo == "PAUSAR")
            mensaje = f"{serie} {'en pausa' if tipo == 'PAUSAR' else 'reanudó su recorrido'}."
        elif tipo in extras:
            mensaje = await extras[tipo](contenedor, dispositivo, datos.model_dump()) or f"Evento {tipo} aplicado."
        else:
            raise ErrorValidacion.de_campo(
                "tipo", f"Tipo de evento no disponible. Use uno de: {', '.join(disponibles)}."
            )
    except ErrorDispositivo as error:
        raise ErrorReglaNegocio(str(error)) from error
    return EventoDemoSalida(id_dispositivo=id_dispositivo, numero_serie=serie, tipo=tipo, mensaje=mensaje)


@router.post(
    "/tareas/{nombre}/ejecutar",
    response_model=TareaSalida,
    summary="Ejecutar ya una tarea programada (demo)",
    description="Demo. Ejecuta ya una tarea: `iniciar-reservas`, `monitoreo` o `reintento-subidas` (núcleo), y las "
    "de los módulos activos, si los hay. Devuelve qué hizo. Una tarea que no existe (o de un módulo apagado) "
    "responde 404.",
)
async def ejecutar_tarea(nombre: str, _: ModoDemo, __: Administrador, contenedor: ContenedorDep) -> TareaSalida:
    tarea = todas_las_tareas(contenedor).get(nombre)
    if tarea is None or not tarea.ejecutable_en_demo:
        raise ErrorNoEncontrado(f"No existe la tarea «{nombre}».")
    return TareaSalida(tarea=nombre, resultado=resumir(await tarea.funcion(contenedor)))
