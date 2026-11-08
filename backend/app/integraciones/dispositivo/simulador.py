"""``ApiDispositivoSimulada`` (RESTR01): todos los robots y drones simulados en memoria.

- **Estado por dispositivo:** posición, batería, sensores, misión, fase, pausa, parada, desvío y carga. Se carga
  solo desde la base la primera vez que se consulta un número de serie (RNF10).
- **Tiempo:** no hay un hilo propio. En cada consulta el estado avanza desde la última vez hasta
  ``reloj.ahora()``. Así es determinista con el ``RelojSimulado`` de las pruebas y exacto con el reloj real.
- **Misión** (``enviar_orden_inicio``): base → origen → destino → base, sin repetir puntos, en
  ``FRACCION_RECORRIDO`` × la duración estimada. El robot recorre todo en ese tiempo; si la orden pide esperar el
  código (RF24), espera en el destino (``ESPERANDO_CODIGO``); si no, deja el pedido y vuelve. El drone vuela la
  mitad del tiempo y graba en el destino (``EN_DESTINO``) la otra mitad.
- **Eventos al servidor:** ``CODIGO_INGRESADO`` y ``LLEGADA_BASE`` van a una cola en memoria (``esperar_evento``).
- **Datos precargados** (``escenario.json``): consumo y recarga de batería, rutas con puntos intermedios, desvío
  para salir de la zona y probabilidad de fallas aleatorias (0 por defecto: determinista).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Protocol

from app.dominio.geometria import distancia_m
from app.integraciones.dispositivo.carga import DatosDispositivo
from app.integraciones.dispositivo.interfaz import (
    ErrorDispositivo,
    EventoDispositivo,
    Fase,
    IApiDispositivo,
    OrdenInicio,
    Punto,
    Reanudacion,
    ResultadoEntrega,
    TelemetriaDispositivo,
    TipoEvento,
)
from app.nucleo.enums import EstadoDispositivo, EstadoSensor, TipoDispositivo, TipoOrden
from app.nucleo.reloj import Reloj

registro = logging.getLogger(__name__)

CARPETA = Path(__file__).resolve().parent
RUTA_ESCENARIO = CARPETA / "escenario.json"
BASE_POR_DEFECTO = Punto(0.0, 0.0, "Sin base configurada")
_MISMO_PUNTO_M = 0.5  # dos puntos a menos de medio metro son el mismo


class Cargador(Protocol):
    async def dispositivo(self, numero_serie: str) -> DatosDispositivo | None: ...

    async def base(self) -> Punto | None: ...


# ============================================================================ escenario (datos precargados)


@dataclass(frozen=True)
class Escenario:
    consumo_por_min: dict[TipoDispositivo, float]
    recarga_por_min: float
    probabilidad_falla_sensor_por_min: float
    desvio_salida_zona: tuple[float, float]
    rutas: dict[tuple[str, str], tuple[Punto, ...]]
    video_muestra: Path

    @classmethod
    def cargar(cls, ruta: Path = RUTA_ESCENARIO) -> Escenario:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        rutas: dict[tuple[str, str], tuple[Punto, ...]] = {}
        for r in datos.get("rutas", []):
            rutas[(r["desde"], r["hasta"])] = tuple(Punto(float(lat), float(lon)) for lat, lon in r["puntos"])
        desvio = datos.get("desvio_salida_zona", {})
        return cls(
            consumo_por_min={TipoDispositivo(t): float(v) for t, v in datos["consumo_bateria_por_min"].items()},
            recarga_por_min=float(datos["recarga_por_min"]),
            probabilidad_falla_sensor_por_min=float(datos.get("probabilidad_falla_sensor_por_min", 0)),
            desvio_salida_zona=(float(desvio.get("latitud", 0.03)), float(desvio.get("longitud", 0.0))),
            rutas=rutas,
            video_muestra=ruta.parent / datos.get("video_muestra", "muestra.mp4"),
        )

    def puntos_intermedios(self, desde: Punto, hasta: Punto) -> tuple[Punto, ...]:
        """Puntos precargados entre dos ubicaciones (en cualquier sentido). Sin ruta precargada: línea recta."""
        if (desde.nombre, hasta.nombre) in self.rutas:
            return self.rutas[(desde.nombre, hasta.nombre)]
        if (hasta.nombre, desde.nombre) in self.rutas:
            return tuple(reversed(self.rutas[(hasta.nombre, desde.nombre)]))
        return ()


# ============================================================================ geometría de la ruta


def _distancia(a: Punto, b: Punto) -> float:
    return distancia_m((a.latitud, a.longitud), (b.latitud, b.longitud))


def _largo(puntos: list[Punto]) -> float:
    return sum(_distancia(a, b) for a, b in pairwise(puntos))


def _posicion(puntos: list[Punto], recorrido: float) -> Punto:
    """Punto de la poligonal después de recorrer ``recorrido`` metros."""
    for a, b in pairwise(puntos):
        tramo = _distancia(a, b)
        if recorrido <= tramo:
            f = 0.0 if tramo == 0 else recorrido / tramo
            return Punto(a.latitud + (b.latitud - a.latitud) * f, a.longitud + (b.longitud - a.longitud) * f)
        recorrido -= tramo
    return puntos[-1]


def _resto(puntos: list[Punto], recorrido: float) -> list[Punto]:
    """Vértices que faltan después de recorrer ``recorrido`` metros."""
    acumulado = 0.0
    faltan: list[Punto] = []
    for a, b in pairwise(puntos):
        acumulado += _distancia(a, b)
        if acumulado > recorrido:
            faltan.append(b)
    return faltan or [puntos[-1]]


def _sin_repetidos(puntos: list[Punto]) -> list[Punto]:
    limpios: list[Punto] = []
    for p in puntos:
        if not limpios or _distancia(limpios[-1], p) >= _MISMO_PUNTO_M:
            limpios.append(p)
    return limpios


# ============================================================================ misión


@dataclass
class Etapa:
    """Un tramo de la misión: moverse por una poligonal (2+ puntos) o quedarse en un punto (1 punto)."""

    fase: Fase
    puntos: list[Punto]
    duracion: float  # segundos; math.inf = hasta que llegue una confirmación (RF24)

    @property
    def es_movimiento(self) -> bool:
        return len(self.puntos) >= 2


@dataclass
class Mision:
    id_reserva: int
    etapas: list[Etapa]
    velocidad_mps: float
    indice: int = 0
    transcurrido: float = 0.0  # segundos dentro de la etapa actual

    @property
    def etapa(self) -> Etapa:
        return self.etapas[self.indice]

    def ubicar_en_el_tiempo(self, segundos: float) -> tuple[int, float]:
        """Etapa y avance (en segundos) que tendría la misión ``segundos`` después de salir, sin pausas."""
        for indice, etapa in enumerate(self.etapas):
            if segundos < etapa.duracion:
                return indice, max(0.0, segundos)
            segundos -= etapa.duracion
        return len(self.etapas), 0.0


@dataclass
class EstadoSimulado:
    numero_serie: str
    tipo: TipoDispositivo
    bateria: float
    sensores: dict[str, EstadoSensor]
    latitud: float
    longitud: float
    ultima: datetime  # hasta cuándo está calculado el estado
    mision: Mision | None = None
    pausado: bool = False  # control de demo: provoca RETRASO
    detenido: bool = False  # PARADA_EMERGENCIA (RF14) hasta un RETORNO_BASE
    desviado: bool = False  # control de demo: fuera de la zona de operación (RF25)
    cargando: bool = False
    desconectado: bool = False  # pruebas: el dispositivo no responde
    codigos: list[str] = field(default_factory=list)
    video_listo: bool = False
    segundos_sin_falla: float = 0.0

    @property
    def fase(self) -> Fase:
        if self.mision is None:
            return Fase.EN_BASE
        if self.detenido:
            return Fase.DETENIDO
        return self.mision.etapa.fase


# ============================================================================ simulador


class ApiDispositivoSimulada(IApiDispositivo):
    def __init__(
        self,
        reloj: Reloj,
        cargador: Cargador,
        *,
        fraccion_recorrido: float = 0.8,
        escenario: Escenario | None = None,
        semilla: int = 42,
    ) -> None:
        self._reloj = reloj
        self._cargador = cargador
        self._fraccion = fraccion_recorrido
        self.escenario = escenario or Escenario.cargar()
        self.datos_precargados = str(RUTA_ESCENARIO)  # atributo del diagrama de clases
        self._azar = random.Random(semilla)
        self._estados: dict[str, EstadoSimulado] = {}
        self._base: Punto | None = None
        self._eventos: asyncio.Queue[EventoDispositivo] = asyncio.Queue()
        self._candado = asyncio.Lock()
        self._video: bytes | None = None

    # ------------------------------------------------------------------ estado

    async def punto_base(self) -> Punto:
        if self._base is None:
            base = await self._cargador.base()
            if base is None:
                registro.warning("No existe la ubicación base en el catálogo; el simulador usa (0, 0).")
                return BASE_POR_DEFECTO
            self._base = base
        return self._base

    async def _estado(self, numero_serie: str) -> EstadoSimulado:
        estado = self._estados.get(numero_serie)
        if estado is None:
            async with self._candado:
                estado = self._estados.get(numero_serie)
                if estado is None:
                    estado = await self._cargar(numero_serie)
                    self._estados[numero_serie] = estado
        if estado.desconectado:
            raise ErrorDispositivo(f"El dispositivo {numero_serie} no responde.")
        self._avanzar(estado)
        return estado

    async def _cargar(self, numero_serie: str) -> EstadoSimulado:
        datos = await self._cargador.dispositivo(numero_serie)
        if datos is None:
            raise ErrorDispositivo(f"El dispositivo {numero_serie} no responde (no está registrado).")
        base = await self.punto_base()
        return EstadoSimulado(
            numero_serie=numero_serie,
            tipo=datos.tipo,
            bateria=float(datos.nivel_bateria),
            sensores=dict(datos.sensores),
            latitud=base.latitud,
            longitud=base.longitud,
            ultima=self._reloj.ahora(),
            cargando=datos.estado == EstadoDispositivo.EN_CARGA,
        )

    def olvidar(self, numero_serie: str | None = None) -> None:
        """Descarta el estado en memoria (de uno o de todos) para volver a leerlo de la base."""
        if numero_serie is None:
            self._estados.clear()
            self._base = None
        else:
            self._estados.pop(numero_serie, None)

    def en_mision(self, numero_serie: str) -> bool:
        estado = self._estados.get(numero_serie)
        return estado is not None and estado.mision is not None

    # ------------------------------------------------------------------ paso del tiempo

    def _avanzar(self, estado: EstadoSimulado) -> None:
        ahora = self._reloj.ahora()
        dt = (ahora - estado.ultima).total_seconds()
        if dt <= 0:
            return
        momento = estado.ultima
        estado.ultima = ahora
        if estado.mision is None:
            if estado.cargando:
                estado.bateria = min(100.0, estado.bateria + self.escenario.recarga_por_min * dt / 60)
                estado.cargando = estado.bateria < 100
            return
        self._fallas_aleatorias(estado, dt)
        while dt > 0 and estado.mision is not None:
            if estado.pausado or estado.detenido:
                self._consumir(estado, dt)
                return
            mision = estado.mision
            etapa = mision.etapa
            paso = min(dt, etapa.duracion - mision.transcurrido)
            mision.transcurrido += paso
            dt -= paso
            momento += timedelta(seconds=paso)
            self._consumir(estado, paso)
            self._ubicar(estado)
            if mision.transcurrido >= etapa.duracion:
                self._siguiente_etapa(estado, momento)

    def _consumir(self, estado: EstadoSimulado, segundos: float) -> None:
        consumo = self.escenario.consumo_por_min.get(estado.tipo, 1.0)
        estado.bateria = max(0.0, estado.bateria - consumo * segundos / 60)

    def _ubicar(self, estado: EstadoSimulado) -> None:
        assert estado.mision is not None
        mision = estado.mision
        etapa = mision.etapa
        if etapa.es_movimiento:
            punto = _posicion(etapa.puntos, mision.transcurrido * mision.velocidad_mps)
        else:
            punto = etapa.puntos[0]
        estado.latitud, estado.longitud = punto.latitud, punto.longitud

    def _siguiente_etapa(self, estado: EstadoSimulado, momento: datetime) -> None:
        assert estado.mision is not None
        estado.mision.indice += 1
        estado.mision.transcurrido = 0.0
        if estado.mision.indice >= len(estado.mision.etapas):
            self._llegar_a_base(estado, momento)

    def _llegar_a_base(self, estado: EstadoSimulado, momento: datetime) -> None:
        base = self._base or BASE_POR_DEFECTO
        estado.latitud, estado.longitud = base.latitud, base.longitud
        estado.mision = None
        estado.pausado = estado.detenido = False
        estado.cargando = estado.bateria < 100
        estado.video_listo = True
        self._eventos.put_nowait(EventoDispositivo(estado.numero_serie, TipoEvento.LLEGADA_BASE, momento))

    def _fallas_aleatorias(self, estado: EstadoSimulado, segundos: float) -> None:
        probabilidad = self.escenario.probabilidad_falla_sensor_por_min
        if probabilidad <= 0:
            return
        estado.segundos_sin_falla += segundos
        while estado.segundos_sin_falla >= 60:
            estado.segundos_sin_falla -= 60
            sanos = [n for n, e in estado.sensores.items() if e == EstadoSensor.OK]
            if sanos and self._azar.random() < probabilidad:
                estado.sensores[self._azar.choice(sanos)] = EstadoSensor.FALLA

    # ------------------------------------------------------------------ plan de la misión

    def _trazar(self, paradas: list[Punto]) -> list[Punto]:
        puntos: list[Punto] = []
        for a, b in pairwise(paradas):
            puntos += [a, *self.escenario.puntos_intermedios(a, b)]
        puntos.append(paradas[-1])
        return _sin_repetidos(puntos)

    def _planear(self, tipo: TipoDispositivo, orden: OrdenInicio, base: Punto) -> Mision:
        ida = self._trazar([base, orden.origen, orden.destino])
        vuelta = self._trazar([orden.destino, base])
        presupuesto = max(1.0, self._fraccion * orden.duracion_estimada_min * 60)
        es_drone = tipo == TipoDispositivo.DRONE
        tiempo_movimiento = presupuesto / 2 if es_drone else presupuesto
        largo_total = _largo(ida) + _largo(vuelta)
        velocidad = largo_total / tiempo_movimiento if largo_total > 0 else 1.0

        etapas: list[Etapa] = []
        if len(ida) >= 2:
            etapas.append(Etapa(Fase.EN_RUTA, ida, _largo(ida) / velocidad))
        if es_drone:
            etapas.append(Etapa(Fase.EN_DESTINO, [orden.destino], presupuesto / 2))
        elif orden.esperar_codigo:
            etapas.append(Etapa(Fase.ESPERANDO_CODIGO, [orden.destino], math.inf))
        if len(vuelta) >= 2:
            etapas.append(Etapa(Fase.RETORNANDO, vuelta, _largo(vuelta) / velocidad))
        if not etapas:
            etapas.append(Etapa(Fase.RETORNANDO, [base], 1.0))
        return Mision(orden.id_reserva, etapas, velocidad)

    def _regreso_directo(self, id_reserva: int, desde: Punto, base: Punto, velocidad: float) -> Mision:
        tramo = _sin_repetidos([desde, base])
        if len(tramo) < 2:
            return Mision(id_reserva, [Etapa(Fase.RETORNANDO, [base], 0.0)], velocidad)
        return Mision(id_reserva, [Etapa(Fase.RETORNANDO, tramo, _largo(tramo) / velocidad)], velocidad)

    def _reanudar(self, plan: Mision, datos: Reanudacion, base: Punto, estado: EstadoSimulado) -> Mision:
        """Retoma la misión desde el último punto guardado (decisión P1)."""
        if datos.ultimo_punto is None or datos.hora_ultimo_punto is None:
            return plan  # sin puntos: sale otra vez desde la base
        punto = datos.ultimo_punto
        estado.latitud, estado.longitud = punto.latitud, punto.longitud
        if datos.regresando or datos.fase_reportada == Fase.RETORNANDO:
            return self._regreso_directo(plan.id_reserva, punto, base, plan.velocidad_mps)
        if datos.fase_reportada == Fase.DETENIDO:
            estado.detenido = True  # sigue detenido hasta que reciba un RETORNO_BASE
            return self._regreso_directo(plan.id_reserva, punto, base, plan.velocidad_mps)
        segundos = (datos.hora_ultimo_punto - datos.hora_salida).total_seconds()
        indice, avance = plan.ubicar_en_el_tiempo(segundos)
        if indice >= len(plan.etapas):
            return self._regreso_directo(plan.id_reserva, punto, base, plan.velocidad_mps)
        etapa = plan.etapas[indice]
        if etapa.es_movimiento:
            resto = _sin_repetidos([punto, *_resto(etapa.puntos, avance * plan.velocidad_mps)])
            primera = Etapa(etapa.fase, resto, _largo(resto) / plan.velocidad_mps if len(resto) >= 2 else 0.0)
        else:
            primera = Etapa(etapa.fase, [punto], etapa.duracion - avance)
        return Mision(plan.id_reserva, [primera, *plan.etapas[indice + 1 :]], plan.velocidad_mps)

    # ------------------------------------------------------------------ IApiDispositivo

    async def obtener_telemetria(self, numero_serie: str) -> TelemetriaDispositivo:
        estado = await self._estado(numero_serie)
        latitud, longitud = estado.latitud, estado.longitud
        if estado.desviado:
            latitud += self.escenario.desvio_salida_zona[0]
            longitud += self.escenario.desvio_salida_zona[1]
        return TelemetriaDispositivo(
            numero_serie=numero_serie,
            fecha_hora=self._reloj.ahora(),
            latitud=round(latitud, 6),
            longitud=round(longitud, 6),
            nivel_bateria=max(0, min(100, round(estado.bateria))),
            sensores=dict(estado.sensores),
            estado_servicio=estado.fase,
        )

    async def enviar_orden_inicio(self, numero_serie: str, orden: OrdenInicio) -> None:
        estado = await self._estado(numero_serie)
        if estado.mision is not None and orden.reanudacion is None:
            raise ErrorDispositivo(f"El dispositivo {numero_serie} ya está en un servicio.")
        base = await self.punto_base()
        estado.latitud, estado.longitud = base.latitud, base.longitud
        estado.pausado = estado.detenido = estado.cargando = estado.video_listo = False
        estado.codigos.clear()
        plan = self._planear(estado.tipo, orden, base)
        if orden.reanudacion is not None:
            plan = self._reanudar(plan, orden.reanudacion, base, estado)
        estado.mision = plan
        registro.info(
            "Simulador: %s sale con la reserva #%d (%d etapas, %.1f m/s)",
            numero_serie,
            orden.id_reserva,
            len(plan.etapas),
            plan.velocidad_mps,
        )

    async def enviar_orden(self, numero_serie: str, tipo: TipoOrden) -> None:
        estado = await self._estado(numero_serie)
        if estado.mision is None:
            raise ErrorDispositivo(f"El dispositivo {numero_serie} no está en un servicio.")
        if tipo == TipoOrden.PARADA_EMERGENCIA:
            estado.detenido = True
            return
        base = await self.punto_base()
        actual = Punto(estado.latitud, estado.longitud)
        estado.detenido = False
        estado.mision = self._regreso_directo(estado.mision.id_reserva, actual, base, estado.mision.velocidad_mps)
        if estado.mision.etapa.duracion <= 0:
            self._llegar_a_base(estado, self._reloj.ahora())

    async def leer_codigo_entrega(self, numero_serie: str) -> str | None:
        estado = await self._estado(numero_serie)
        return estado.codigos.pop(0) if estado.codigos else None

    async def confirmar_entrega(self, numero_serie: str, resultado: ResultadoEntrega) -> None:
        estado = await self._estado(numero_serie)
        if resultado == ResultadoEntrega.NO_CONFIRMADA:
            return  # sigue esperando otro código
        if estado.mision is not None and estado.mision.etapa.fase == Fase.ESPERANDO_CODIGO:
            self._siguiente_etapa(estado, self._reloj.ahora())

    async def descargar_video(self, numero_serie: str) -> bytes:
        estado = await self._estado(numero_serie)
        if not estado.video_listo:
            raise ErrorDispositivo(f"El dispositivo {numero_serie} no tiene un video listo.")
        if self._video is None:
            self._video = await asyncio.to_thread(self.escenario.video_muestra.read_bytes)
        return self._video

    async def esperar_evento(self) -> EventoDispositivo:
        return await self._eventos.get()

    # ------------------------------------------------------------------ controles (demo y pruebas)

    async def fijar_bateria(self, numero_serie: str, nivel: int) -> None:
        estado = await self._estado(numero_serie)
        estado.bateria = float(max(0, min(100, nivel)))
        estado.cargando = False

    async def fallar_sensor(self, numero_serie: str, sensor: str) -> None:
        await self._cambiar_sensor(numero_serie, sensor, EstadoSensor.FALLA)

    async def reparar_sensor(self, numero_serie: str, sensor: str) -> None:
        await self._cambiar_sensor(numero_serie, sensor, EstadoSensor.OK)

    async def _cambiar_sensor(self, numero_serie: str, sensor: str, estado_sensor: EstadoSensor) -> None:
        estado = await self._estado(numero_serie)
        nombre = next((n for n in estado.sensores if n.lower() == sensor.strip().lower()), None)
        if nombre is None:
            raise ErrorDispositivo(f"El dispositivo {numero_serie} no tiene el sensor «{sensor}».")
        estado.sensores[nombre] = estado_sensor

    async def pausar(self, numero_serie: str, pausado: bool = True) -> None:
        """Detiene el avance de la misión sin cambiar la fase (sirve para provocar un RETRASO)."""
        (await self._estado(numero_serie)).pausado = pausado

    async def desviar(self, numero_serie: str, fuera_de_zona: bool = True) -> None:
        """Mueve la posición reportada fuera de la zona de operación (o la devuelve)."""
        (await self._estado(numero_serie)).desviado = fuera_de_zona

    async def ingresar_codigo(self, numero_serie: str, codigo: str) -> None:
        """Quien recibe digita un código en el robot: el robot avisa al servidor con CODIGO_INGRESADO."""
        estado = await self._estado(numero_serie)
        if estado.fase != Fase.ESPERANDO_CODIGO:
            raise ErrorDispositivo(f"El robot {numero_serie} no está esperando un código de entrega.")
        estado.codigos.append(codigo)
        self._eventos.put_nowait(EventoDispositivo(numero_serie, TipoEvento.CODIGO_INGRESADO, self._reloj.ahora()))

    def desconectar(self, numero_serie: str, desconectado: bool = True) -> None:
        """Pruebas: el dispositivo deja de responder (o vuelve a hacerlo)."""
        estado = self._estados.get(numero_serie)
        if estado is not None:
            estado.desconectado = desconectado
