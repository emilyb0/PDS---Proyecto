"""Contenedor de dependencias: arma una sola vez el reloj, la base, los adaptadores y las extensiones.

La aplicación real lo crea desde la configuración; las pruebas lo arman con adaptadores falsos, un
``RelojSimulado`` y los módulos que necesiten (las del núcleo, con ninguno).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import app.modelos  # noqa: F401  (registra todos los modelos antes de usarlos)
from app.config import Configuracion
from app.integraciones.almacenamiento import IAlmacenamientoCloud, crear_almacenamiento
from app.integraciones.dispositivo.carga import CargadorDesdeBD
from app.integraciones.dispositivo.interfaz import IApiDispositivo
from app.integraciones.dispositivo.simulador import ApiDispositivoSimulada
from app.nucleo.bd import crear_fabrica_sesiones, crear_motor
from app.nucleo.eventos import BusEventos
from app.nucleo.extensiones import REQUISITOS_NUCLEO, Extensiones, ModuloRF
from app.nucleo.reloj import Reloj, RelojSistema
from app.nucleo.seguridad import CifradorContrasenas, EmisorTokens
from app.videos.gestor_videos import GestorVideos

if TYPE_CHECKING:
    from app.servicios.monitor import MonitorServicios


@dataclass
class Contenedor:
    config: Configuracion
    reloj: Reloj
    motor: AsyncEngine
    sesiones: async_sessionmaker[AsyncSession]
    cifrador: CifradorContrasenas
    tokens: EmisorTokens
    api_dispositivo: IApiDispositivo
    almacenamiento: IAlmacenamientoCloud
    gestor_videos: GestorVideos
    bus: BusEventos
    modulos: list[ModuloRF] = field(default_factory=list)
    extensiones: Extensiones = field(default_factory=Extensiones)
    # Se crea en ``crear`` porque necesita el contenedor ya armado.
    monitor: MonitorServicios = field(init=False)

    @classmethod
    def crear(
        cls,
        config: Configuracion,
        *,
        reloj: Reloj | None = None,
        motor: AsyncEngine | None = None,
        modulos: Sequence[ModuloRF] | None = None,
        api_dispositivo: IApiDispositivo | None = None,
        almacenamiento: IAlmacenamientoCloud | None = None,
    ) -> Contenedor:
        if modulos is None:
            # Import diferido: los módulos importan el núcleo, nunca al revés.
            from app.modulos import seleccionar_modulos

            modulos = seleccionar_modulos(config.modulos_activos)
        reloj = reloj or RelojSistema()
        motor = motor or crear_motor(config.url_bd)
        sesiones = crear_fabrica_sesiones(motor)
        api_dispositivo = api_dispositivo or ApiDispositivoSimulada(
            reloj,
            CargadorDesdeBD(sesiones, config.base_ubicacion),
            fraccion_recorrido=config.fraccion_recorrido,
            semilla=config.semilla_simulador,
        )
        almacenamiento = almacenamiento or crear_almacenamiento(config)
        extensiones = Extensiones()
        for modulo in modulos:
            if modulo.configurar is not None:
                modulo.configurar(extensiones, config)
        contenedor = cls(
            config=config,
            reloj=reloj,
            motor=motor,
            sesiones=sesiones,
            cifrador=CifradorContrasenas(config.argon2_iteraciones, config.argon2_memoria_kib),
            tokens=EmisorTokens(config.jwt_secreto, reloj, config.jwt_expira_horas, config.jwt_algoritmo),
            api_dispositivo=api_dispositivo,
            almacenamiento=almacenamiento,
            gestor_videos=GestorVideos(almacenamiento, config.pendientes_dir),
            bus=BusEventos(),
            modulos=list(modulos),
            extensiones=extensiones,
        )
        # Import diferido: el monitor usa servicios que a su vez importan el contenedor.
        from app.servicios.monitor import MonitorServicios

        contenedor.monitor = MonitorServicios(contenedor)
        return contenedor

    @property
    def requisitos_activos(self) -> list[str]:
        """RF del núcleo más los de los módulos activos, en orden."""
        todos = set(REQUISITOS_NUCLEO) | {rf for m in self.modulos for rf in m.requisitos}
        return sorted(todos, key=lambda rf: int(rf.removeprefix("RF")))

    async def cerrar(self) -> None:
        await self.motor.dispose()
