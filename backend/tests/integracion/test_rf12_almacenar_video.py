"""RF12 — Almacenar el video del servicio: al cerrar se sube el MP4 y se asocia a la bitácora.

Si la subida falla, la bitácora se cierra igual, el MP4 queda en la carpeta de pendientes y la tarea
``reintento-subidas`` lo sube después (especificación 7.5).
"""

from __future__ import annotations

from datetime import datetime, time

import httpx
import pytest
from sqlalchemy import select

from app.contenedor import Contenedor
from app.integraciones.almacenamiento import ErrorAlmacenamiento
from app.integraciones.dispositivo.interfaz import ErrorDispositivo
from app.nucleo.enums import TipoDispositivo
from app.servicios import monitor
from app.tareas.catalogo import todas_las_tareas
from app.usuarios.modelos import Usuario
from app.videos.gestor_videos import GestorVideos
from app.videos.modelos import Video
from tests.fabrica import ciclo, crear_ubicaciones, servicio_en_curso


@pytest.fixture
async def lugares(contenedor: Contenedor) -> dict:
    return await crear_ubicaciones(contenedor)


async def test_rf12_el_drone_cierra_y_su_video_queda_asociado_a_la_bitacora(
    cliente: httpx.AsyncClient, contenedor: Contenedor, admin: Usuario, operador: Usuario, lugares: dict, auth
) -> None:
    _, _, id_bitacora = await servicio_en_curso(
        contenedor, administrador=admin, operador=operador, lugares=lugares, tipo=TipoDispositivo.DRONE
    )
    await ciclo(contenedor, minutes=25)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(operador))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["tiene_video"] is True
    assert detalle["video"]["duracion_seg"] == 24 * 60 and detalle["video"]["eliminado"] is False
    ruta_objeto = contenedor.config.almacenamiento_local_dir / "videos" / "2026" / "11" / f"bitacora-{id_bitacora}.mp4"
    assert ruta_objeto.read_bytes()[4:8] == b"ftyp"


async def test_rf12_si_la_subida_falla_queda_pendiente_y_la_tarea_la_sube(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
    monkeypatch,
) -> None:
    original = contenedor.almacenamiento.subir

    async def sin_nube(archivo: bytes, nombre: str) -> str:
        raise ErrorAlmacenamiento("sin conexión")

    monkeypatch.setattr(contenedor.almacenamiento, "subir", sin_nube)
    _, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await ciclo(contenedor, minutes=25)

    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["video"] is None  # se cierra igual
    [pendiente] = contenedor.gestor_videos.pendientes()
    assert pendiente.id_bitacora == id_bitacora and pendiente.duracion_seg == 24 * 60
    assert pendiente.fecha_grabacion == datetime(2026, 11, 9, 10, 0)

    reintento = todas_las_tareas(contenedor)["reintento-subidas"]
    assert await reintento.funcion(contenedor) == {"subidos": 0, "pendientes": 1}  # la nube sigue caída
    monkeypatch.setattr(contenedor.almacenamiento, "subir", original)
    assert await reintento.funcion(contenedor) == {"subidos": 1, "pendientes": 0}
    assert contenedor.gestor_videos.pendientes() == []
    async with contenedor.sesiones() as sesion:
        video = await sesion.scalar(select(Video).where(Video.id_bitacora == id_bitacora))
    assert video is not None and video.duracion_seg == 24 * 60
    assert video.fecha_grabacion == datetime(2026, 11, 9, 10, 0)
    assert video.url == f"local://videos/2026/11/bitacora-{id_bitacora}.mp4"


async def test_rf12_solo_se_guardan_videos_mp4(contenedor: Contenedor) -> None:
    gestor: GestorVideos = contenedor.gestor_videos
    assert await gestor.almacenar_video(1, datetime(2026, 11, 9, 10), 60, b"esto no es un video") is None
    assert gestor.pendientes() == []
    assert GestorVideos.nombre_objeto(12, datetime(2026, 1, 5)) == "videos/2026/01/bitacora-12.mp4"


async def test_rf12_almacenamiento_local_guarda_lee_por_rango_y_borra(contenedor: Contenedor) -> None:
    almacenamiento = contenedor.almacenamiento
    url = await almacenamiento.subir(b"0123456789", "videos/prueba.mp4")
    assert url == "local://videos/prueba.mp4"
    assert await almacenamiento.tamano(url) == 10
    assert await almacenamiento.obtener_rango(url, 2, 5) == b"2345"
    assert await almacenamiento.obtener(url) == b"0123456789"
    await almacenamiento.eliminar(url)
    await almacenamiento.eliminar(url)  # borrar lo que ya no existe no es un error
    with pytest.raises(ErrorAlmacenamiento):
        await almacenamiento.obtener(url)
    with pytest.raises(ErrorAlmacenamiento):
        await almacenamiento.subir(b"x", "../fuera.mp4")


async def test_rf12_la_descarga_del_video_se_reintenta_y_si_no_llega_se_cierra_sin_video(
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    lugares: dict,
    auth,
    monkeypatch,
) -> None:
    monkeypatch.setattr(monitor, "ESPERA_ENTRE_INTENTOS_SEG", 0)
    simulador = contenedor.api_dispositivo
    original = simulador.descargar_video
    fallos = {"pendientes": 2}

    async def a_veces(serie: str) -> bytes:
        if fallos["pendientes"] > 0:
            fallos["pendientes"] -= 1
            raise ErrorDispositivo("se cortó la transferencia")
        return await original(serie)

    monkeypatch.setattr(simulador, "descargar_video", a_veces)
    _, _, primera = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await ciclo(contenedor, minutes=25)
    detalle = (await cliente.get(f"/api/bitacoras/{primera}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["video"] is not None  # llegó al tercer intento

    fallos["pendientes"] = 99
    _, _, segunda = await servicio_en_curso(
        contenedor, administrador=admin, operador=operador, lugares=lugares, hora_inicio=time(11, 0)
    )
    await ciclo(contenedor, minutes=25)
    detalle = (await cliente.get(f"/api/bitacoras/{segunda}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["video"] is None
    assert contenedor.gestor_videos.pendientes() == []
