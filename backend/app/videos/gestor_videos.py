"""``GestorVideos`` del núcleo: guardar el video de cada servicio (RF12, RESTR04).

Al cerrar un servicio (especificación 7.5):

1. ``almacenar_video`` sube el MP4 con ``IAlmacenamientoCloud.subir``, **fuera** de la transacción.
2. ``registrar_video`` crea la fila ``video`` dentro de la transacción del cierre.
3. Si la subida falla, el MP4 queda en la carpeta de pendientes (con un ``.json`` con sus datos) y la tarea
   ``reintento-subidas`` lo vuelve a intentar cada 5 minutos; la fila ``video`` se crea cuando suba.

Buscar videos (``buscar_videos``) y borrar los vencidos (``eliminar_videos_vencidos``) irán en los módulos RF13 y
RF26 (pendientes; decisión M-9).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integraciones.almacenamiento import ErrorAlmacenamiento, IAlmacenamientoCloud
from app.videos.modelos import Video

registro = logging.getLogger(__name__)


def es_mp4(archivo: bytes) -> bool:
    """Un MP4 empieza con la caja ``ftyp`` (bytes 4 a 8)."""
    return len(archivo) > 12 and archivo[4:8] == b"ftyp"


@dataclass(frozen=True)
class VideoPendiente:
    id_bitacora: int
    nombre: str
    fecha_grabacion: datetime
    duracion_seg: int

    def a_json(self) -> str:
        return json.dumps(
            {
                "id_bitacora": self.id_bitacora,
                "nombre": self.nombre,
                "fecha_grabacion": self.fecha_grabacion.isoformat(),
                "duracion_seg": self.duracion_seg,
            },
            ensure_ascii=False,
        )

    @classmethod
    def de_json(cls, texto: str) -> VideoPendiente:
        datos = json.loads(texto)
        return cls(
            id_bitacora=int(datos["id_bitacora"]),
            nombre=str(datos["nombre"]),
            fecha_grabacion=datetime.fromisoformat(datos["fecha_grabacion"]),
            duracion_seg=int(datos["duracion_seg"]),
        )


class GestorVideos:
    def __init__(self, almacenamiento: IAlmacenamientoCloud, carpeta_pendientes: Path) -> None:
        self.almacenamiento = almacenamiento
        self.carpeta_pendientes = Path(carpeta_pendientes)

    @staticmethod
    def nombre_objeto(id_bitacora: int, fecha_grabacion: datetime) -> str:
        return f"videos/{fecha_grabacion:%Y/%m}/bitacora-{id_bitacora}.mp4"

    # ------------------------------------------------------------------ RF12

    async def almacenar_video(
        self, id_bitacora: int, fecha_grabacion: datetime, duracion_seg: int, archivo: bytes
    ) -> str | None:
        """Sube el MP4 y devuelve su ubicación. Si falla, lo deja en pendientes y devuelve ``None``."""
        if not es_mp4(archivo):
            registro.error("El video de la bitácora #%d no es un MP4; no se guarda.", id_bitacora)
            return None
        nombre = self.nombre_objeto(id_bitacora, fecha_grabacion)
        try:
            return await self.almacenamiento.subir(archivo, nombre)
        except ErrorAlmacenamiento as error:
            registro.warning("No se pudo subir el video de la bitácora #%d (%s); queda pendiente.", id_bitacora, error)
            await self.guardar_pendiente(VideoPendiente(id_bitacora, nombre, fecha_grabacion, duracion_seg), archivo)
            return None

    @staticmethod
    def registrar_video(
        sesion: AsyncSession, id_bitacora: int, url: str, fecha_grabacion: datetime, duracion_seg: int
    ) -> Video:
        """Asocia el video al servicio en la transacción en curso (paso 4 de RF12)."""
        video = Video(
            id_bitacora=id_bitacora,
            url=url,
            formato="MP4",
            fecha_grabacion=fecha_grabacion,
            duracion_seg=max(1, duracion_seg),
        )
        sesion.add(video)
        return video

    # ------------------------------------------------------------------ pendientes

    def _rutas(self, id_bitacora: int) -> tuple[Path, Path]:
        base = self.carpeta_pendientes / f"bitacora-{id_bitacora}"
        return base.with_suffix(".mp4"), base.with_suffix(".json")

    async def guardar_pendiente(self, pendiente: VideoPendiente, archivo: bytes) -> None:
        video, datos = self._rutas(pendiente.id_bitacora)

        def escribir() -> None:
            self.carpeta_pendientes.mkdir(parents=True, exist_ok=True)
            video.write_bytes(archivo)
            datos.write_text(pendiente.a_json(), encoding="utf-8")  # el .json se escribe al final

        try:
            await asyncio.to_thread(escribir)
        except OSError:
            registro.exception("No se pudo guardar el video pendiente de la bitácora #%d", pendiente.id_bitacora)

    def pendientes(self) -> list[VideoPendiente]:
        if not self.carpeta_pendientes.is_dir():
            return []
        encontrados = []
        for ruta in sorted(self.carpeta_pendientes.glob("bitacora-*.json")):
            try:
                encontrados.append(VideoPendiente.de_json(ruta.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError):
                registro.exception("Archivo de video pendiente dañado: %s", ruta)
        return encontrados

    async def reintentar_subidas(self, sesiones: async_sessionmaker[AsyncSession]) -> dict[str, int]:
        """Tarea ``reintento-subidas`` (cada 5 min): sube los pendientes y crea su fila ``video``."""
        subidos = 0
        lista = self.pendientes()
        for pendiente in lista:
            ruta_video, ruta_datos = self._rutas(pendiente.id_bitacora)
            try:
                archivo = await asyncio.to_thread(ruta_video.read_bytes)
                url = await self.almacenamiento.subir(archivo, pendiente.nombre)
            except (OSError, ErrorAlmacenamiento) as error:
                registro.warning("Sigue pendiente el video de la bitácora #%d: %s", pendiente.id_bitacora, error)
                continue
            async with sesiones() as sesion:
                ya_existe = await sesion.scalar(
                    select(Video.id_video).where(Video.id_bitacora == pendiente.id_bitacora)
                )
                if ya_existe is None:
                    self.registrar_video(
                        sesion, pendiente.id_bitacora, url, pendiente.fecha_grabacion, pendiente.duracion_seg
                    )
                    await sesion.commit()
            ruta_datos.unlink(missing_ok=True)
            ruta_video.unlink(missing_ok=True)
            subidos += 1
            registro.info("Se subió el video pendiente de la bitácora #%d", pendiente.id_bitacora)
        return {"subidos": subidos, "pendientes": len(lista) - subidos}
