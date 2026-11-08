"""Catálogo de tareas: las del núcleo más las que registran los módulos activos (``Extensiones.tareas``).

| Tarea | Frecuencia | RF |
|---|---|---|
| ``iniciar-reservas`` | cada 10 s | RF08 |
| ``monitoreo`` | cada ``INTERVALO_MONITOREO_SEG`` | RF09–RF11 (y RF25 cuando exista) |
| ``reintento-subidas`` | cada 5 min | RF12 |
| ``mantenimiento-preventivo`` | diaria 06:00 | RF16 (módulo pendiente) |
| ``retencion-videos`` | diaria 02:00 | RF26 (módulo pendiente) |

Los controles de demo (``POST /api/demo/tareas/{nombre}/ejecutar``) usan estas mismas funciones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.nucleo.extensiones import TareaProgramada

if TYPE_CHECKING:
    from app.contenedor import Contenedor


async def iniciar_reservas(contenedor: Contenedor) -> dict[str, int]:
    return await contenedor.monitor.iniciar_reservas_pendientes()


async def monitoreo(contenedor: Contenedor) -> dict[str, int]:
    return {"dispositivos": await contenedor.monitor.actualizar_monitoreo()}


async def reintento_subidas(contenedor: Contenedor) -> dict[str, int]:
    return await contenedor.gestor_videos.reintentar_subidas(contenedor.sesiones)


def tareas_del_nucleo(contenedor: Contenedor) -> list[TareaProgramada]:
    return [
        TareaProgramada("iniciar-reservas", iniciar_reservas, "intervalo", segundos=10),
        TareaProgramada("monitoreo", monitoreo, "intervalo", segundos=contenedor.config.intervalo_monitoreo_seg),
        TareaProgramada("reintento-subidas", reintento_subidas, "intervalo", segundos=300),
    ]


def todas_las_tareas(contenedor: Contenedor) -> dict[str, TareaProgramada]:
    return {t.nombre: t for t in [*tareas_del_nucleo(contenedor), *contenedor.extensiones.tareas]}


def resumir(resultado: Any) -> Any:
    """Resumen JSON de lo que hizo una tarea (para el control de demo)."""
    if resultado is None or isinstance(resultado, dict | int | str):
        return resultado
    if isinstance(resultado, list | tuple):
        return {"elementos": len(resultado)}
    return str(resultado)
